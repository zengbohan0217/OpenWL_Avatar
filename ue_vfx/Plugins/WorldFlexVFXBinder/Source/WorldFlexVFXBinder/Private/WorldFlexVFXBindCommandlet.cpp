#include "WorldFlexVFXBindCommandlet.h"

#include "Animation/AnimSequence.h"
#include "Dom/JsonObject.h"
#include "Engine/SkeletalMesh.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "NiagaraSystem.h"
#include "Policies/PrettyJsonPrintPolicy.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "WorldFlexVFXBinderLibrary.h"

namespace
{
bool ParseBoolParam(const TCHAR* Stream, const TCHAR* Name, bool bDefault)
{
    FString Value;
    if (!FParse::Value(Stream, Name, Value))
    {
        return bDefault;
    }

    return Value.Equals(TEXT("true"), ESearchCase::IgnoreCase)
        || Value.Equals(TEXT("1"))
        || Value.Equals(TEXT("yes"), ESearchCase::IgnoreCase);
}

EWorldFlexVFXRuleType ParseRuleType(const FString& Rule)
{
    if (Rule.Equals(TEXT("impact"), ESearchCase::IgnoreCase)
        || Rule.Equals(TEXT("speed_peak"), ESearchCase::IgnoreCase)
        || Rule.Equals(TEXT("speed_peak_impact"), ESearchCase::IgnoreCase))
    {
        return EWorldFlexVFXRuleType::SpeedPeakImpact;
    }

    if (Rule.Equals(TEXT("fixed"), ESearchCase::IgnoreCase)
        || Rule.Equals(TEXT("fixed_frame"), ESearchCase::IgnoreCase))
    {
        return EWorldFlexVFXRuleType::FixedFrame;
    }

    if (Rule.Equals(TEXT("run"), ESearchCase::IgnoreCase)
        || Rule.Equals(TEXT("run_loop"), ESearchCase::IgnoreCase))
    {
        return EWorldFlexVFXRuleType::RunLoop;
    }

    return EWorldFlexVFXRuleType::SpeedTrail;
}

FString RuleTypeToString(EWorldFlexVFXRuleType RuleType)
{
    switch (RuleType)
    {
    case EWorldFlexVFXRuleType::SpeedPeakImpact: return TEXT("speed_peak_impact");
    case EWorldFlexVFXRuleType::RunLoop:         return TEXT("run_loop");
    case EWorldFlexVFXRuleType::FixedFrame:      return TEXT("fixed_frame");
    case EWorldFlexVFXRuleType::SpeedTrail:
    default:                                     return TEXT("speed_trail");
    }
}

FVector ParseVectorField(const TSharedPtr<FJsonObject>& JsonObject, const FString& FieldName, const FVector& Default)
{
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!JsonObject->TryGetArrayField(FieldName, Values) || !Values || Values->Num() != 3)
    {
        return Default;
    }

    return FVector(
        (*Values)[0]->AsNumber(),
        (*Values)[1]->AsNumber(),
        (*Values)[2]->AsNumber());
}

/** Rotation array convention: [pitch, yaw, roll] in degrees. */
FRotator ParseRotatorField(const TSharedPtr<FJsonObject>& JsonObject, const FString& FieldName, const FRotator& Default)
{
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!JsonObject->TryGetArrayField(FieldName, Values) || !Values || Values->Num() != 3)
    {
        return Default;
    }

    return FRotator(
        (*Values)[0]->AsNumber(),
        (*Values)[1]->AsNumber(),
        (*Values)[2]->AsNumber());
}

bool BuildRuleFromJson(const TSharedPtr<FJsonObject>& JsonRule, FWorldFlexVFXRule& OutRule, FString& OutError)
{
    FString RuleName;
    JsonRule->TryGetStringField(TEXT("rule"), RuleName);
    OutRule.RuleType = ParseRuleType(RuleName);

    FString BoneName;
    if (!JsonRule->TryGetStringField(TEXT("bone"), BoneName) || BoneName.IsEmpty())
    {
        OutError = TEXT("rule is missing 'bone'");
        return false;
    }
    OutRule.BoneName = FName(*BoneName);

    FString NiagaraPath;
    if (!JsonRule->TryGetStringField(TEXT("niagara"), NiagaraPath) || NiagaraPath.IsEmpty())
    {
        OutError = TEXT("rule is missing 'niagara'");
        return false;
    }

    UNiagaraSystem* NiagaraSystem = LoadObject<UNiagaraSystem>(nullptr, *NiagaraPath);
    if (!NiagaraSystem)
    {
        OutError = FString::Printf(TEXT("failed to load Niagara system: %s"), *NiagaraPath);
        return false;
    }
    OutRule.NiagaraSystem = NiagaraSystem;

    double NumberValue = 0.0;
    if (JsonRule->TryGetNumberField(TEXT("speed_threshold"), NumberValue))
    {
        OutRule.SpeedThreshold = static_cast<float>(NumberValue);
    }
    if (JsonRule->TryGetNumberField(TEXT("min_duration"), NumberValue))
    {
        OutRule.MinDuration = static_cast<float>(NumberValue);
    }
    if (JsonRule->TryGetNumberField(TEXT("offset_after_peak"), NumberValue))
    {
        OutRule.OffsetAfterPeakSeconds = static_cast<float>(NumberValue);
    }
    if (JsonRule->TryGetNumberField(TEXT("frame"), NumberValue))
    {
        OutRule.FixedFrame = static_cast<int32>(NumberValue);
    }

    bool bBoolValue = false;
    if (JsonRule->TryGetBoolField(TEXT("horizontal_only"), bBoolValue))
    {
        OutRule.bHorizontalOnly = bBoolValue;
    }

    OutRule.LocationOffset = ParseVectorField(JsonRule, TEXT("location_offset"), FVector::ZeroVector);
    OutRule.RotationOffset = ParseRotatorField(JsonRule, TEXT("rotation_offset"), FRotator::ZeroRotator);
    OutRule.Scale = ParseVectorField(JsonRule, TEXT("scale"), FVector(1.0f));
    return true;
}

struct FBindingRequest
{
    FString AnimPath;
    FString MeshPath;
    FString EventsJsonPath;
    FName TrackName = FName(TEXT("WorldFlexVFX"));
    bool bRemoveExisting = false;
    TArray<FWorldFlexVFXRule> Rules;
    TArray<FString> RuleErrors;
};

TArray<TSharedPtr<FJsonValue>> EventsToJson(const TArray<FWorldFlexVFXEvent>& Events)
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
    return JsonEvents;
}

TArray<TSharedPtr<FJsonValue>> StatsToJson(
    const TArray<FWorldFlexVFXRule>& Rules,
    const TArray<FWorldFlexVFXRuleStats>& Stats)
{
    TArray<TSharedPtr<FJsonValue>> JsonStats;
    for (int32 Index = 0; Index < Stats.Num(); ++Index)
    {
        const FWorldFlexVFXRuleStats& Stat = Stats[Index];
        TSharedRef<FJsonObject> JsonStat = MakeShared<FJsonObject>();
        JsonStat->SetStringField(TEXT("rule"), RuleTypeToString(Stat.RuleType));
        JsonStat->SetStringField(TEXT("bone"), Stat.BoneName.ToString());
        if (Rules.IsValidIndex(Index) && Rules[Index].NiagaraSystem)
        {
            JsonStat->SetStringField(TEXT("niagara"), Rules[Index].NiagaraSystem->GetPathName());
        }
        JsonStat->SetNumberField(TEXT("used_threshold"), Stat.UsedThreshold);
        JsonStat->SetNumberField(TEXT("max_speed"), Stat.MaxSpeed);
        JsonStat->SetNumberField(TEXT("mean_speed"), Stat.MeanSpeed);
        JsonStat->SetNumberField(TEXT("p90_speed"), Stat.P90Speed);
        JsonStat->SetNumberField(TEXT("peak_frame"), Stat.PeakFrame);
        JsonStat->SetNumberField(TEXT("suggested_threshold"), Stat.SuggestedThreshold);
        JsonStat->SetNumberField(TEXT("event_count"), Stat.EventCount);

        if (Stat.SpeedCurve.Num() > 0)
        {
            TArray<TSharedPtr<FJsonValue>> Curve;
            Curve.Reserve(Stat.SpeedCurve.Num());
            for (const float Speed : Stat.SpeedCurve)
            {
                Curve.Add(MakeShared<FJsonValueNumber>(Speed));
            }
            JsonStat->SetArrayField(TEXT("speed_curve"), Curve);
        }

        JsonStats.Add(MakeShared<FJsonValueObject>(JsonStat));
    }
    return JsonStats;
}

TSharedRef<FJsonObject> ProcessBinding(
    const FBindingRequest& Request,
    const bool bApply,
    const bool bCollectCurves,
    int32& InOutFailureCount,
    int32& InOutTotalEventCount)
{
    TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("anim"), Request.AnimPath);
    Report->SetStringField(TEXT("mesh"), Request.MeshPath);
    Report->SetStringField(TEXT("track"), Request.TrackName.ToString());
    Report->SetBoolField(TEXT("remove_existing"), Request.bRemoveExisting);

    bool bBindingFailed = false;

    if (Request.RuleErrors.Num() > 0)
    {
        TArray<TSharedPtr<FJsonValue>> Errors;
        for (const FString& Error : Request.RuleErrors)
        {
            Errors.Add(MakeShared<FJsonValueString>(Error));
            UE_LOG(LogTemp, Error, TEXT("WorldFlexVFXBind: [%s] %s"), *Request.AnimPath, *Error);
        }
        Report->SetArrayField(TEXT("rule_errors"), Errors);
        bBindingFailed = true;
    }

    UAnimSequence* Animation = LoadObject<UAnimSequence>(nullptr, *Request.AnimPath);
    if (!Animation)
    {
        UE_LOG(LogTemp, Error, TEXT("WorldFlexVFXBind: failed to load animation: %s"), *Request.AnimPath);
        Report->SetStringField(TEXT("status"), TEXT("error_load_anim"));
        ++InOutFailureCount;
        return Report;
    }

    USkeletalMesh* PreviewMesh = nullptr;
    if (!Request.MeshPath.IsEmpty())
    {
        PreviewMesh = LoadObject<USkeletalMesh>(nullptr, *Request.MeshPath);
        if (!PreviewMesh)
        {
            UE_LOG(LogTemp, Warning, TEXT("WorldFlexVFXBind: failed to load preview mesh, continuing without it: %s"), *Request.MeshPath);
        }
    }

    Report->SetNumberField(TEXT("play_length"), Animation->GetPlayLength());
    Report->SetNumberField(TEXT("frame_count"), Animation->GetNumberOfSampledKeys());

    TArray<FWorldFlexVFXEvent> Events;
    TArray<FWorldFlexVFXRuleStats> Stats;
    UWorldFlexVFXBinderLibrary::DetectVFXEventsWithStats(
        Animation, PreviewMesh, Request.Rules, bCollectCurves, Events, Stats);

    InOutTotalEventCount += Events.Num();
    Report->SetArrayField(TEXT("rules"), StatsToJson(Request.Rules, Stats));
    Report->SetArrayField(TEXT("events"), EventsToJson(Events));

    if (!Request.EventsJsonPath.IsEmpty())
    {
        UWorldFlexVFXBinderLibrary::ExportVFXEventsToJson(Events, Request.EventsJsonPath);
        Report->SetStringField(TEXT("events_json"), Request.EventsJsonPath);
        UE_LOG(LogTemp, Display, TEXT("WorldFlexVFXBind: exported %d event(s) to %s"), Events.Num(), *Request.EventsJsonPath);
    }

    if (bApply && Events.Num() > 0)
    {
        const bool bApplied = UWorldFlexVFXBinderLibrary::ApplyVFXEventsToAnimation(
            Animation, Events, Request.TrackName, Request.bRemoveExisting);

        Report->SetBoolField(TEXT("applied"), bApplied);
        Report->SetStringField(TEXT("status"), bApplied ? TEXT("applied") : TEXT("error_apply"));
        if (!bApplied)
        {
            bBindingFailed = true;
        }
        UE_LOG(LogTemp, Display, TEXT("WorldFlexVFXBind: [%s] apply=%s events=%d"),
            *Request.AnimPath, bApplied ? TEXT("true") : TEXT("false"), Events.Num());
    }
    else
    {
        Report->SetBoolField(TEXT("applied"), false);
        Report->SetStringField(TEXT("status"), Events.Num() > 0 ? TEXT("detected") : TEXT("no_events"));
        if (Events.Num() == 0)
        {
            UE_LOG(LogTemp, Warning, TEXT("WorldFlexVFXBind: no VFX events detected for %s (check 'suggested_threshold' in report)"), *Request.AnimPath);
        }
    }

    if (bBindingFailed)
    {
        ++InOutFailureCount;
    }

    return Report;
}

/** Resolves a possibly-relative path against the rules file directory. */
FString ResolvePath(const FString& Path, const FString& BaseDir)
{
    if (Path.IsEmpty() || !FPaths::IsRelative(Path))
    {
        return Path;
    }
    return FPaths::Combine(BaseDir, Path);
}

bool LoadRequestsFromRulesFile(
    const FString& RulesPath,
    TArray<FBindingRequest>& OutRequests,
    FString& OutError)
{
    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *RulesPath))
    {
        OutError = FString::Printf(TEXT("failed to read rules file: %s"), *RulesPath);
        return false;
    }

    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        OutError = FString::Printf(TEXT("failed to parse rules JSON: %s"), *RulesPath);
        return false;
    }

    FString GlobalTrack = TEXT("WorldFlexVFX");
    Root->TryGetStringField(TEXT("track"), GlobalTrack);

    bool bGlobalRemoveExisting = false;
    Root->TryGetBoolField(TEXT("remove_existing"), bGlobalRemoveExisting);

    const TArray<TSharedPtr<FJsonValue>>* Bindings = nullptr;
    if (!Root->TryGetArrayField(TEXT("bindings"), Bindings) || !Bindings || Bindings->Num() == 0)
    {
        OutError = TEXT("rules file has no 'bindings' array");
        return false;
    }

    const FString BaseDir = FPaths::GetPath(RulesPath);

    for (const TSharedPtr<FJsonValue>& BindingValue : *Bindings)
    {
        const TSharedPtr<FJsonObject>* BindingObject = nullptr;
        if (!BindingValue->TryGetObject(BindingObject) || !BindingObject->IsValid())
        {
            continue;
        }

        FBindingRequest Request;
        if (!(*BindingObject)->TryGetStringField(TEXT("anim"), Request.AnimPath) || Request.AnimPath.IsEmpty())
        {
            OutError = TEXT("a binding entry is missing 'anim'");
            return false;
        }

        (*BindingObject)->TryGetStringField(TEXT("mesh"), Request.MeshPath);

        FString EventsJson;
        if ((*BindingObject)->TryGetStringField(TEXT("events_json"), EventsJson))
        {
            Request.EventsJsonPath = ResolvePath(EventsJson, BaseDir);
        }

        FString Track = GlobalTrack;
        (*BindingObject)->TryGetStringField(TEXT("track"), Track);
        Request.TrackName = FName(*Track);

        Request.bRemoveExisting = bGlobalRemoveExisting;
        bool bRemove = false;
        if ((*BindingObject)->TryGetBoolField(TEXT("remove_existing"), bRemove))
        {
            Request.bRemoveExisting = bRemove;
        }

        const TArray<TSharedPtr<FJsonValue>>* Rules = nullptr;
        if ((*BindingObject)->TryGetArrayField(TEXT("rules"), Rules) && Rules)
        {
            for (const TSharedPtr<FJsonValue>& RuleValue : *Rules)
            {
                const TSharedPtr<FJsonObject>* RuleObject = nullptr;
                if (!RuleValue->TryGetObject(RuleObject) || !RuleObject->IsValid())
                {
                    continue;
                }

                FWorldFlexVFXRule Rule;
                FString RuleError;
                if (BuildRuleFromJson(*RuleObject, Rule, RuleError))
                {
                    Request.Rules.Add(Rule);
                }
                else
                {
                    Request.RuleErrors.Add(RuleError);
                }
            }
        }

        OutRequests.Add(MoveTemp(Request));
    }

    return OutRequests.Num() > 0;
}

bool SaveReport(const TSharedRef<FJsonObject>& Report, const FString& ReportPath)
{
    FString OutputJson;
    const TSharedRef<TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>> Writer =
        TJsonWriterFactory<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>::Create(&OutputJson);
    if (!FJsonSerializer::Serialize(Report, Writer))
    {
        return false;
    }
    return FFileHelper::SaveStringToFile(OutputJson, *ReportPath);
}
}

UWorldFlexVFXBindCommandlet::UWorldFlexVFXBindCommandlet()
{
    IsClient = false;
    IsEditor = true;
    IsServer = false;
    LogToConsole = true;
}

int32 UWorldFlexVFXBindCommandlet::Main(const FString& Params)
{
    const bool bApply = ParseBoolParam(*Params, TEXT("Apply="), true);
    const bool bCollectCurves = ParseBoolParam(*Params, TEXT("Curves="), false);

    FString RulesPath;
    FParse::Value(*Params, TEXT("Rules="), RulesPath);

    FString ReportPath;
    FParse::Value(*Params, TEXT("Report="), ReportPath);

    TArray<FBindingRequest> Requests;

    if (!RulesPath.IsEmpty())
    {
        // ---- Batch mode: rules JSON drives everything. ----
        FString Error;
        if (!LoadRequestsFromRulesFile(RulesPath, Requests, Error))
        {
            UE_LOG(LogTemp, Error, TEXT("WorldFlexVFXBind: %s"), *Error);
            return 1;
        }

        if (ReportPath.IsEmpty())
        {
            ReportPath = FPaths::Combine(FPaths::GetPath(RulesPath), TEXT("bind_report.json"));
        }
    }
    else
    {
        // ---- Legacy single-rule mode (backwards compatible). ----
        FString AnimPath;
        FString MeshPath;
        FString NiagaraPath;
        FString BoneName;
        FString RuleName;
        FString TrackName;
        FString JsonPath;

        FParse::Value(*Params, TEXT("Anim="), AnimPath);
        FParse::Value(*Params, TEXT("Mesh="), MeshPath);
        FParse::Value(*Params, TEXT("Niagara="), NiagaraPath);
        FParse::Value(*Params, TEXT("Bone="), BoneName);
        FParse::Value(*Params, TEXT("Rule="), RuleName);
        FParse::Value(*Params, TEXT("Track="), TrackName);
        FParse::Value(*Params, TEXT("Json="), JsonPath);

        if (AnimPath.IsEmpty() || NiagaraPath.IsEmpty() || BoneName.IsEmpty())
        {
            UE_LOG(LogTemp, Error, TEXT(
                "Missing required params.\n"
                "Batch:  -run=WorldFlexVFXBind -Rules=D:/path/vfx_rules.json [-Apply=true] [-Curves=true] [-Report=D:/path/bind_report.json]\n"
                "Single: -run=WorldFlexVFXBind -Anim=/Game/... -Niagara=/Game/... -Bone=RightFoot [-Mesh=/Game/...] "
                "[-Rule=speed_trail|impact|run_loop|fixed_frame] [-Speed=350] [-MinDuration=0.08] [-OffsetAfterPeak=0.06] "
                "[-Frame=14] [-HorizontalOnly=false] [-Apply=true] [-Json=D:/events.json] [-Report=D:/bind_report.json]"));
            return 1;
        }

        UNiagaraSystem* NiagaraSystem = LoadObject<UNiagaraSystem>(nullptr, *NiagaraPath);
        if (!NiagaraSystem)
        {
            UE_LOG(LogTemp, Error, TEXT("Failed to load Niagara system: %s"), *NiagaraPath);
            return 3;
        }

        FWorldFlexVFXRule Rule;
        Rule.RuleType = ParseRuleType(RuleName);
        Rule.BoneName = FName(*BoneName);
        Rule.NiagaraSystem = NiagaraSystem;
        FParse::Value(*Params, TEXT("Speed="), Rule.SpeedThreshold);
        FParse::Value(*Params, TEXT("MinDuration="), Rule.MinDuration);
        FParse::Value(*Params, TEXT("OffsetAfterPeak="), Rule.OffsetAfterPeakSeconds);
        FParse::Value(*Params, TEXT("Frame="), Rule.FixedFrame);
        Rule.bHorizontalOnly = ParseBoolParam(*Params, TEXT("HorizontalOnly="), false);

        FBindingRequest Request;
        Request.AnimPath = AnimPath;
        Request.MeshPath = MeshPath;
        Request.EventsJsonPath = JsonPath;
        Request.TrackName = TrackName.IsEmpty() ? FName(TEXT("WorldFlexVFX")) : FName(*TrackName);
        Request.bRemoveExisting = ParseBoolParam(*Params, TEXT("RemoveExisting="), false);
        Request.Rules.Add(Rule);
        Requests.Add(MoveTemp(Request));
    }

    // ---- Process all bindings and build the report. ----
    TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("generated_at"), FDateTime::Now().ToIso8601());
    Report->SetStringField(TEXT("rules_file"), RulesPath);
    Report->SetBoolField(TEXT("apply"), bApply);

    int32 FailureCount = 0;
    int32 TotalEventCount = 0;
    TArray<TSharedPtr<FJsonValue>> BindingReports;
    for (const FBindingRequest& Request : Requests)
    {
        BindingReports.Add(MakeShared<FJsonValueObject>(
            ProcessBinding(Request, bApply, bCollectCurves, FailureCount, TotalEventCount)));
    }
    Report->SetArrayField(TEXT("bindings"), BindingReports);
    Report->SetNumberField(TEXT("total_events"), TotalEventCount);
    Report->SetNumberField(TEXT("failures"), FailureCount);

    if (!ReportPath.IsEmpty())
    {
        if (SaveReport(Report, ReportPath))
        {
            UE_LOG(LogTemp, Display, TEXT("WorldFlexVFXBind: report written to %s"), *ReportPath);
        }
        else
        {
            UE_LOG(LogTemp, Error, TEXT("WorldFlexVFXBind: failed to write report to %s"), *ReportPath);
        }
    }

    if (FailureCount > 0)
    {
        return 1;
    }
    return TotalEventCount > 0 ? 0 : 5;
}
