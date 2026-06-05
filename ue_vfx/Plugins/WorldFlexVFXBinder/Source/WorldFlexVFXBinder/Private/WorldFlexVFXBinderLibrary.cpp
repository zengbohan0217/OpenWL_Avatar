#include "WorldFlexVFXBinderLibrary.h"

#include "Algo/Reverse.h"
#include "Animation/AnimSequence.h"
#include "Animation/Skeleton.h"
#include "AnimationBlueprintLibrary.h"
#include "AnimNotify_PlayNiagaraEffect.h"
#include "AnimNotifyState_TimedNiagaraEffect.h"
#include "Dom/JsonObject.h"
#include "EditorAssetLibrary.h"
#include "Engine/SkeletalMesh.h"
#include "Misc/FileHelper.h"
#include "ReferenceSkeleton.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
int32 GetFrameCount(const UAnimSequence* Animation)
{
    if (!Animation)
    {
        return 0;
    }

    const int32 NumKeys = Animation->GetNumberOfSampledKeys();
    if (NumKeys > 0)
    {
        return NumKeys;
    }

    const double FrameRate = Animation->GetSamplingFrameRate().AsDecimal();
    return FMath::Max(1, FMath::RoundToInt(
        Animation->GetPlayLength() * (FrameRate > 0.0 ? static_cast<float>(FrameRate) : 30.0f)));
}

float FrameToTime(const UAnimSequence* Animation, int32 Frame)
{
    const int32 FrameCount = GetFrameCount(Animation);
    if (!Animation || FrameCount <= 1)
    {
        return 0.0f;
    }

    return Animation->GetPlayLength() * static_cast<float>(Frame) / static_cast<float>(FrameCount - 1);
}

/**
 * Samples bone trajectories in COMPONENT SPACE by accumulating local-space
 * transforms along the reference-skeleton hierarchy.
 *
 * Rationale: GetBonePosesForFrame returns local (parent-relative) transforms.
 * For deep bones like RightFoot the local translation is essentially the
 * constant bone length, so differentiating it yields no usable speed signal.
 * Accumulating root->bone gives a physically meaningful trajectory in cm,
 * so speeds are real cm/s and thresholds become calibratable.
 */
struct FWorldFlexBoneSampler
{
    const UAnimSequence* Animation = nullptr;
    USkeletalMesh* PreviewMesh = nullptr;
    int32 FrameCount = 0;
    float DeltaTime = 0.0f;

    // Cache: bone name -> component-space position per frame.
    TMap<FName, TArray<FVector>> PositionCache;

    bool Init(const UAnimSequence* InAnimation, USkeletalMesh* InPreviewMesh)
    {
        Animation = InAnimation;
        PreviewMesh = InPreviewMesh;
        if (!Animation)
        {
            return false;
        }

        FrameCount = GetFrameCount(Animation);
        if (FrameCount < 2)
        {
            return false;
        }

        DeltaTime = Animation->GetPlayLength() / static_cast<float>(FrameCount - 1);
        return DeltaTime > KINDA_SMALL_NUMBER;
    }

    const FReferenceSkeleton* GetReferenceSkeleton() const
    {
        if (PreviewMesh)
        {
            return &PreviewMesh->GetRefSkeleton();
        }

        if (Animation)
        {
            if (const USkeleton* Skeleton = Animation->GetSkeleton())
            {
                return &Skeleton->GetReferenceSkeleton();
            }
        }

        return nullptr;
    }

    /** Builds the bone chain from root to BoneName (inclusive), root first. */
    bool BuildBoneChain(const FName BoneName, TArray<FName>& OutChainRootFirst) const
    {
        const FReferenceSkeleton* RefSkeleton = GetReferenceSkeleton();
        if (!RefSkeleton)
        {
            return false;
        }

        int32 BoneIndex = RefSkeleton->FindBoneIndex(BoneName);
        if (BoneIndex == INDEX_NONE)
        {
            return false;
        }

        OutChainRootFirst.Reset();
        while (BoneIndex != INDEX_NONE)
        {
            OutChainRootFirst.Add(RefSkeleton->GetBoneName(BoneIndex));
            BoneIndex = RefSkeleton->GetParentIndex(BoneIndex);
        }

        Algo::Reverse(OutChainRootFirst);
        return true;
    }

    /** Returns component-space positions for every frame; cached per bone. */
    const TArray<FVector>* GetComponentSpacePositions(const FName BoneName)
    {
        if (const TArray<FVector>* Cached = PositionCache.Find(BoneName))
        {
            return Cached;
        }

        TArray<FName> Chain;
        if (!BuildBoneChain(BoneName, Chain))
        {
            UE_LOG(LogTemp, Error,
                TEXT("WorldFlexVFX: bone '%s' not found in reference skeleton."),
                *BoneName.ToString());
            return nullptr;
        }

        TArray<FVector> Positions;
        Positions.Reserve(FrameCount);

        for (int32 Frame = 0; Frame < FrameCount; ++Frame)
        {
            TArray<FTransform> LocalPoses;
            // GetBonePosesForFrame is deprecated in UE5.7 but still functional.
            // Centralised here so a future migration to AnimPose / AnimationDataModel
            // only needs to touch this one call site.
            PRAGMA_DISABLE_DEPRECATION_WARNINGS
            UAnimationBlueprintLibrary::GetBonePosesForFrame(
                Animation,
                Chain,
                Frame,
                /*bExtractRootMotion=*/ false,
                LocalPoses,
                PreviewMesh);
            PRAGMA_ENABLE_DEPRECATION_WARNINGS

            if (LocalPoses.Num() != Chain.Num())
            {
                UE_LOG(LogTemp, Error,
                    TEXT("WorldFlexVFX: pose evaluation failed for bone '%s' at frame %d (%d/%d poses)."),
                    *BoneName.ToString(), Frame, LocalPoses.Num(), Chain.Num());
                return nullptr;
            }

            // Accumulate root -> leaf: ChildComponent = ChildLocal * ParentComponent.
            FTransform ComponentTransform = FTransform::Identity;
            for (int32 Index = 0; Index < LocalPoses.Num(); ++Index)
            {
                ComponentTransform = LocalPoses[Index] * ComponentTransform;
            }

            Positions.Add(ComponentTransform.GetLocation());
        }

        return &PositionCache.Add(BoneName, MoveTemp(Positions));
    }

    /** Per-frame speed in cm/s. Entry 0 duplicates entry 1 to keep array sizes aligned with frames. */
    bool GetSpeedCurve(const FName BoneName, const bool bHorizontalOnly, TArray<float>& OutSpeeds)
    {
        const TArray<FVector>* Positions = GetComponentSpacePositions(BoneName);
        if (!Positions || Positions->Num() < 2)
        {
            return false;
        }

        OutSpeeds.Reset();
        OutSpeeds.Reserve(Positions->Num());
        OutSpeeds.Add(0.0f); // placeholder, fixed below

        for (int32 Frame = 1; Frame < Positions->Num(); ++Frame)
        {
            FVector Delta = (*Positions)[Frame] - (*Positions)[Frame - 1];
            if (bHorizontalOnly)
            {
                Delta.Z = 0.0f;
            }
            OutSpeeds.Add(Delta.Size() / DeltaTime);
        }

        OutSpeeds[0] = OutSpeeds.Num() > 1 ? OutSpeeds[1] : 0.0f;
        return true;
    }
};

FWorldFlexVFXRuleStats MakeRuleStats(
    const FWorldFlexVFXRule& Rule,
    const TArray<float>& Speeds,
    const bool bKeepCurve)
{
    FWorldFlexVFXRuleStats Stats;
    Stats.RuleType = Rule.RuleType;
    Stats.BoneName = Rule.BoneName;
    Stats.UsedThreshold = Rule.SpeedThreshold;

    if (Speeds.Num() == 0)
    {
        return Stats;
    }

    float Sum = 0.0f;
    for (int32 Frame = 0; Frame < Speeds.Num(); ++Frame)
    {
        Sum += Speeds[Frame];
        if (Speeds[Frame] > Stats.MaxSpeed)
        {
            Stats.MaxSpeed = Speeds[Frame];
            Stats.PeakFrame = Frame;
        }
    }
    Stats.MeanSpeed = Sum / static_cast<float>(Speeds.Num());

    TArray<float> Sorted = Speeds;
    Sorted.Sort();
    const int32 P90Index = FMath::Clamp(
        FMath::FloorToInt(0.9f * static_cast<float>(Sorted.Num() - 1)), 0, Sorted.Num() - 1);
    Stats.P90Speed = Sorted[P90Index];

    Stats.SuggestedThreshold = 0.5f * (Stats.MeanSpeed + Stats.MaxSpeed);

    if (bKeepCurve)
    {
        Stats.SpeedCurve = Speeds;
    }

    return Stats;
}

void AddBurstEvent(
    const UAnimSequence* Animation,
    const FWorldFlexVFXRule& Rule,
    const EWorldFlexVFXEventType EventType,
    const int32 Frame,
    TArray<FWorldFlexVFXEvent>& OutEvents)
{
    FWorldFlexVFXEvent Event;
    Event.EventType = EventType;
    Event.BoneName = Rule.BoneName;
    Event.NiagaraSystem = Rule.NiagaraSystem;
    Event.Frame = FMath::Clamp(Frame, 0, FMath::Max(0, GetFrameCount(Animation) - 1));
    Event.Time = FrameToTime(Animation, Event.Frame);
    Event.Duration = 0.0f;
    Event.LocationOffset = Rule.LocationOffset;
    Event.RotationOffset = Rule.RotationOffset;
    Event.Scale = Rule.Scale;
    OutEvents.Add(Event);
}

void AddLoopingEvent(
    const UAnimSequence* Animation,
    const FWorldFlexVFXRule& Rule,
    const int32 StartFrame,
    const int32 EndFrame,
    TArray<FWorldFlexVFXEvent>& OutEvents)
{
    FWorldFlexVFXEvent Event;
    Event.EventType = EWorldFlexVFXEventType::Looping;
    Event.BoneName = Rule.BoneName;
    Event.NiagaraSystem = Rule.NiagaraSystem;
    Event.Frame = StartFrame;
    Event.Time = FrameToTime(Animation, StartFrame);
    Event.Duration = FrameToTime(Animation, EndFrame) - Event.Time;
    Event.LocationOffset = Rule.LocationOffset;
    Event.RotationOffset = Rule.RotationOffset;
    Event.Scale = Rule.Scale;
    OutEvents.Add(Event);
}

void DetectFixedFrame(
    const UAnimSequence* Animation,
    const FWorldFlexVFXRule& Rule,
    TArray<FWorldFlexVFXEvent>& OutEvents)
{
    AddBurstEvent(Animation, Rule, EWorldFlexVFXEventType::Burst, Rule.FixedFrame, OutEvents);
}

void DetectSpeedPeakImpact(
    const UAnimSequence* Animation,
    FWorldFlexBoneSampler& Sampler,
    const FWorldFlexVFXRule& Rule,
    const TArray<float>& Speeds,
    TArray<FWorldFlexVFXEvent>& OutEvents)
{
    // Impact semantics: fast motion that stops abruptly (a hit landing, a foot
    // planting, a body landing from a jump). Among all frames above the speed
    // threshold, pick the one with the steepest deceleration over the next few
    // frames — NOT the raw global speed peak. A run-up or jump take-off can have
    // a higher peak than the landing, but it decays gradually; the actual impact
    // is where the speed curve falls off a cliff.
    const int32 LookAheadFrames = 3;
    float BestDrop = 0.0f;
    float BestSpeed = 0.0f;
    int32 BestFrame = INDEX_NONE;

    for (int32 Frame = 1; Frame < Speeds.Num(); ++Frame)
    {
        if (Speeds[Frame] < Rule.SpeedThreshold)
        {
            continue;
        }

        float MinAfter = Speeds[Frame];
        const int32 LastFrame = FMath::Min(Frame + LookAheadFrames, Speeds.Num() - 1);
        for (int32 Ahead = Frame + 1; Ahead <= LastFrame; ++Ahead)
        {
            MinAfter = FMath::Min(MinAfter, Speeds[Ahead]);
        }

        const float Drop = Speeds[Frame] - MinAfter;
        if (Drop > BestDrop)
        {
            BestDrop = Drop;
            BestSpeed = Speeds[Frame];
            BestFrame = Frame;
        }
    }

    UE_LOG(LogTemp, Display,
        TEXT("WorldFlexVFX SpeedPeakImpact: Bone=%s Threshold=%.1f ImpactFrame=%d Speed=%.1f Drop=%.1f cm/s"),
        *Rule.BoneName.ToString(), Rule.SpeedThreshold, BestFrame, BestSpeed, BestDrop);

    if (BestFrame != INDEX_NONE)
    {
        const int32 OffsetFrames = FMath::RoundToInt(
            Rule.OffsetAfterPeakSeconds / FMath::Max(Sampler.DeltaTime, KINDA_SMALL_NUMBER));
        AddBurstEvent(Animation, Rule, EWorldFlexVFXEventType::Impact, BestFrame + OffsetFrames, OutEvents);
    }
}

void DetectSpeedTrail(
    const UAnimSequence* Animation,
    FWorldFlexBoneSampler& Sampler,
    const FWorldFlexVFXRule& Rule,
    const TArray<float>& Speeds,
    TArray<FWorldFlexVFXEvent>& OutEvents)
{
    const int32 MinFrames = FMath::Max(1, FMath::RoundToInt(
        Rule.MinDuration / FMath::Max(Sampler.DeltaTime, KINDA_SMALL_NUMBER)));

    // Hysteresis: enter the trail at the full threshold, exit at 80% of it,
    // so speeds oscillating around the threshold don't fragment into many short trails.
    const float ExitThreshold = Rule.SpeedThreshold * 0.8f;

    int32 LocalEventCount = 0;
    bool bInTrail = Speeds[0] >= Rule.SpeedThreshold;
    int32 TrailStartFrame = 0;

    for (int32 Frame = 1; Frame < Speeds.Num(); ++Frame)
    {
        if (!bInTrail && Speeds[Frame] >= Rule.SpeedThreshold)
        {
            bInTrail = true;
            TrailStartFrame = Frame;
        }
        else if (bInTrail && Speeds[Frame] < ExitThreshold)
        {
            if (Frame - TrailStartFrame >= MinFrames)
            {
                AddLoopingEvent(Animation, Rule, TrailStartFrame, Frame, OutEvents);
                ++LocalEventCount;
            }
            bInTrail = false;
        }
    }

    if (bInTrail)
    {
        const int32 TrailEndFrame = Speeds.Num() - 1;
        if (TrailEndFrame - TrailStartFrame >= MinFrames)
        {
            AddLoopingEvent(Animation, Rule, TrailStartFrame, TrailEndFrame, OutEvents);
            ++LocalEventCount;
        }
    }

    UE_LOG(LogTemp, Display,
        TEXT("WorldFlexVFX SpeedTrail: Bone=%s Threshold=%.1f cm/s MinFrames=%d Events=%d"),
        *Rule.BoneName.ToString(), Rule.SpeedThreshold, MinFrames, LocalEventCount);
}
}

bool UWorldFlexVFXBinderLibrary::DetectVFXEvents(
    UAnimSequence* Animation,
    USkeletalMesh* PreviewMesh,
    const TArray<FWorldFlexVFXRule>& Rules,
    TArray<FWorldFlexVFXEvent>& OutEvents)
{
    TArray<FWorldFlexVFXRuleStats> UnusedStats;
    return DetectVFXEventsWithStats(Animation, PreviewMesh, Rules, false, OutEvents, UnusedStats);
}

bool UWorldFlexVFXBinderLibrary::DetectVFXEventsWithStats(
    UAnimSequence* Animation,
    USkeletalMesh* PreviewMesh,
    const TArray<FWorldFlexVFXRule>& Rules,
    bool bCollectSpeedCurves,
    TArray<FWorldFlexVFXEvent>& OutEvents,
    TArray<FWorldFlexVFXRuleStats>& OutStats)
{
    OutEvents.Reset();
    OutStats.Reset();
    if (!Animation)
    {
        return false;
    }

    FWorldFlexBoneSampler Sampler;
    const bool bSamplerReady = Sampler.Init(Animation, PreviewMesh);

    for (const FWorldFlexVFXRule& Rule : Rules)
    {
        FWorldFlexVFXRuleStats Stats;
        Stats.RuleType = Rule.RuleType;
        Stats.BoneName = Rule.BoneName;
        Stats.UsedThreshold = Rule.SpeedThreshold;

        if (!Rule.NiagaraSystem || Rule.BoneName.IsNone())
        {
            OutStats.Add(Stats);
            continue;
        }

        if (Rule.RuleType == EWorldFlexVFXRuleType::FixedFrame)
        {
            DetectFixedFrame(Animation, Rule, OutEvents);
            Stats.EventCount = 1;
            OutStats.Add(Stats);
            continue;
        }

        // Speed-based rules need the sampler.
        TArray<float> Speeds;
        // RunLoop defaults to horizontal-only locomotion speed unless overridden.
        const bool bHorizontalOnly =
            Rule.bHorizontalOnly || Rule.RuleType == EWorldFlexVFXRuleType::RunLoop;

        if (!bSamplerReady || !Sampler.GetSpeedCurve(Rule.BoneName, bHorizontalOnly, Speeds))
        {
            UE_LOG(LogTemp, Warning,
                TEXT("WorldFlexVFX: could not sample bone '%s'; rule skipped."),
                *Rule.BoneName.ToString());
            OutStats.Add(Stats);
            continue;
        }

        const int32 EventCountBefore = OutEvents.Num();
        switch (Rule.RuleType)
        {
        case EWorldFlexVFXRuleType::SpeedTrail:
        case EWorldFlexVFXRuleType::RunLoop:
            DetectSpeedTrail(Animation, Sampler, Rule, Speeds, OutEvents);
            break;
        case EWorldFlexVFXRuleType::SpeedPeakImpact:
            DetectSpeedPeakImpact(Animation, Sampler, Rule, Speeds, OutEvents);
            break;
        default:
            break;
        }

        Stats = MakeRuleStats(Rule, Speeds, bCollectSpeedCurves);
        Stats.EventCount = OutEvents.Num() - EventCountBefore;
        OutStats.Add(Stats);
    }

    OutEvents.Sort([](const FWorldFlexVFXEvent& A, const FWorldFlexVFXEvent& B)
    {
        return A.Time < B.Time;
    });

    return OutEvents.Num() > 0;
}

bool UWorldFlexVFXBinderLibrary::ApplyVFXEventsToAnimation(
    UAnimSequenceBase* Animation,
    const TArray<FWorldFlexVFXEvent>& Events,
    FName NotifyTrackName,
    bool bRemoveExistingTrackEvents)
{
    if (!Animation)
    {
        return false;
    }

    if (NotifyTrackName.IsNone())
    {
        NotifyTrackName = TEXT("WorldFlexVFX");
    }

    Animation->Modify();

    if (bRemoveExistingTrackEvents && UAnimationBlueprintLibrary::IsValidAnimNotifyTrackName(Animation, NotifyTrackName))
    {
        UAnimationBlueprintLibrary::RemoveAnimationNotifyEventsByTrack(Animation, NotifyTrackName);
    }

    if (!UAnimationBlueprintLibrary::IsValidAnimNotifyTrackName(Animation, NotifyTrackName))
    {
        UAnimationBlueprintLibrary::AddAnimationNotifyTrack(Animation, NotifyTrackName, FLinearColor::Yellow);
    }

    int32 AddedCount = 0;
    for (const FWorldFlexVFXEvent& Event : Events)
    {
        const bool bIsTimedEvent = Event.Duration > KINDA_SMALL_NUMBER || Event.EventType == EWorldFlexVFXEventType::Looping;
        const bool bAdded = bIsTimedEvent
            ? AddTimedNiagaraNotify(Animation, Event, NotifyTrackName)
            : AddNiagaraNotify(Animation, Event, NotifyTrackName);

        if (bAdded)
        {
            ++AddedCount;
        }
    }

    if (AddedCount > 0)
    {
        Animation->MarkPackageDirty();
        UEditorAssetLibrary::SaveLoadedAsset(Animation, false);
    }
    return AddedCount > 0;
}

bool UWorldFlexVFXBinderLibrary::DetectAndApplyVFXEvents(
    UAnimSequence* Animation,
    USkeletalMesh* PreviewMesh,
    const TArray<FWorldFlexVFXRule>& Rules,
    FName NotifyTrackName,
    bool bRemoveExistingTrackEvents,
    TArray<FWorldFlexVFXEvent>& OutEvents)
{
    if (!DetectVFXEvents(Animation, PreviewMesh, Rules, OutEvents))
    {
        return false;
    }

    return ApplyVFXEventsToAnimation(Animation, OutEvents, NotifyTrackName, bRemoveExistingTrackEvents);
}

bool UWorldFlexVFXBinderLibrary::ExportVFXEventsToJson(
    const TArray<FWorldFlexVFXEvent>& Events,
    const FString& OutputFile)
{
    TArray<TSharedPtr<FJsonValue>> JsonEvents;

    for (const FWorldFlexVFXEvent& Event : Events)
    {
        TSharedRef<FJsonObject> JsonEvent = MakeShared<FJsonObject>();
        JsonEvent->SetNumberField(TEXT("frame"), Event.Frame);
        JsonEvent->SetNumberField(TEXT("time"), Event.Time);
        JsonEvent->SetNumberField(TEXT("duration"), Event.Duration);
        JsonEvent->SetStringField(TEXT("type"), StaticEnum<EWorldFlexVFXEventType>()->GetNameStringByValue(static_cast<int64>(Event.EventType)));
        JsonEvent->SetStringField(TEXT("bone"), Event.BoneName.ToString());
        JsonEvent->SetStringField(TEXT("niagara"), Event.NiagaraSystem ? Event.NiagaraSystem->GetPathName() : FString());
        JsonEvents.Add(MakeShared<FJsonValueObject>(JsonEvent));
    }

    FString OutputJson;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputJson);
    FJsonSerializer::Serialize(JsonEvents, Writer);
    return FFileHelper::SaveStringToFile(OutputJson, *OutputFile);
}

bool UWorldFlexVFXBinderLibrary::AddNiagaraNotify(
    UAnimSequenceBase* Animation,
    const FWorldFlexVFXEvent& Event,
    FName NotifyTrackName)
{
    if (!Animation || !Event.NiagaraSystem)
    {
        return false;
    }

    UAnimNotify* Notify = UAnimationBlueprintLibrary::AddAnimationNotifyEvent(
        Animation,
        NotifyTrackName,
        Event.Time,
        UAnimNotify_PlayNiagaraEffect::StaticClass());

    UAnimNotify_PlayNiagaraEffect* NiagaraNotify = Cast<UAnimNotify_PlayNiagaraEffect>(Notify);
    if (!NiagaraNotify)
    {
        return false;
    }

    NiagaraNotify->Template = Event.NiagaraSystem;
    NiagaraNotify->Attached = true;
    NiagaraNotify->SocketName = Event.BoneName;
    NiagaraNotify->LocationOffset = Event.LocationOffset;
    NiagaraNotify->RotationOffset = Event.RotationOffset;
    NiagaraNotify->Scale = Event.Scale.IsNearlyZero() ? FVector(1.0f) : Event.Scale;
    return true;
}

bool UWorldFlexVFXBinderLibrary::AddTimedNiagaraNotify(
    UAnimSequenceBase* Animation,
    const FWorldFlexVFXEvent& Event,
    FName NotifyTrackName)
{
    if (!Animation || !Event.NiagaraSystem)
    {
        return false;
    }

    const float Duration = FMath::Max(Event.Duration, 0.05f);
    UAnimNotifyState* NotifyState = UAnimationBlueprintLibrary::AddAnimationNotifyStateEvent(
        Animation,
        NotifyTrackName,
        Event.Time,
        Duration,
        UAnimNotifyState_TimedNiagaraEffect::StaticClass());

    UAnimNotifyState_TimedNiagaraEffect* NiagaraNotifyState = Cast<UAnimNotifyState_TimedNiagaraEffect>(NotifyState);
    if (!NiagaraNotifyState)
    {
        return false;
    }

    NiagaraNotifyState->Template = Event.NiagaraSystem;
    NiagaraNotifyState->SocketName = Event.BoneName;
    NiagaraNotifyState->LocationOffset = Event.LocationOffset;
    NiagaraNotifyState->RotationOffset = Event.RotationOffset;
    NiagaraNotifyState->Scale = Event.Scale.IsNearlyZero() ? FVector(1.0f) : Event.Scale;
    NiagaraNotifyState->bDestroyAtEnd = false;
    return true;
}
