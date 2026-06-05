#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "WorldFlexVFXBinderTypes.h"
#include "WorldFlexVFXBinderLibrary.generated.h"

class UAnimSequence;
class UAnimSequenceBase;
class USkeletalMesh;

UCLASS()
class WORLDFLEXVFXBINDER_API UWorldFlexVFXBinderLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, CallInEditor, Category = "WorldFlex VFX")
    static bool DetectVFXEvents(
        UAnimSequence* Animation,
        USkeletalMesh* PreviewMesh,
        const TArray<FWorldFlexVFXRule>& Rules,
        TArray<FWorldFlexVFXEvent>& OutEvents);

    /** Same as DetectVFXEvents but also returns per-rule speed statistics
        (component space, cm/s) for threshold calibration. OutStats is parallel to Rules.
        When bCollectSpeedCurves is true each stats entry also carries the per-frame speed curve. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category = "WorldFlex VFX")
    static bool DetectVFXEventsWithStats(
        UAnimSequence* Animation,
        USkeletalMesh* PreviewMesh,
        const TArray<FWorldFlexVFXRule>& Rules,
        bool bCollectSpeedCurves,
        TArray<FWorldFlexVFXEvent>& OutEvents,
        TArray<FWorldFlexVFXRuleStats>& OutStats);

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "WorldFlex VFX")
    static bool ApplyVFXEventsToAnimation(
        UAnimSequenceBase* Animation,
        const TArray<FWorldFlexVFXEvent>& Events,
        FName NotifyTrackName,
        bool bRemoveExistingTrackEvents);

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "WorldFlex VFX")
    static bool DetectAndApplyVFXEvents(
        UAnimSequence* Animation,
        USkeletalMesh* PreviewMesh,
        const TArray<FWorldFlexVFXRule>& Rules,
        FName NotifyTrackName,
        bool bRemoveExistingTrackEvents,
        TArray<FWorldFlexVFXEvent>& OutEvents);

    UFUNCTION(BlueprintCallable, Category = "WorldFlex VFX")
    static bool ExportVFXEventsToJson(
        const TArray<FWorldFlexVFXEvent>& Events,
        const FString& OutputFile);

private:
    static bool AddNiagaraNotify(
        UAnimSequenceBase* Animation,
        const FWorldFlexVFXEvent& Event,
        FName NotifyTrackName);

    static bool AddTimedNiagaraNotify(
        UAnimSequenceBase* Animation,
        const FWorldFlexVFXEvent& Event,
        FName NotifyTrackName);
};
