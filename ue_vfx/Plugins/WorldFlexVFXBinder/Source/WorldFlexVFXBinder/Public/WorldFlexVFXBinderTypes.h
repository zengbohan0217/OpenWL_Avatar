#pragma once

#include "CoreMinimal.h"
#include "NiagaraSystem.h"
#include "WorldFlexVFXBinderTypes.generated.h"

UENUM(BlueprintType)
enum class EWorldFlexVFXRuleType : uint8
{
    SpeedTrail UMETA(DisplayName = "Speed Trail"),
    SpeedPeakImpact UMETA(DisplayName = "Speed Peak Impact"),
    RunLoop UMETA(DisplayName = "Run Loop"),
    FixedFrame UMETA(DisplayName = "Fixed Frame")
};

UENUM(BlueprintType)
enum class EWorldFlexVFXEventType : uint8
{
    TrailStart UMETA(DisplayName = "Trail Start"),
    TrailEnd UMETA(DisplayName = "Trail End"),
    Impact UMETA(DisplayName = "Impact"),
    Looping UMETA(DisplayName = "Looping"),
    Burst UMETA(DisplayName = "Burst")
};

USTRUCT(BlueprintType)
struct FWorldFlexVFXRule
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    EWorldFlexVFXRuleType RuleType = EWorldFlexVFXRuleType::SpeedTrail;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    FName BoneName = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    TObjectPtr<UNiagaraSystem> NiagaraSystem = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    float SpeedThreshold = 120.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    float MinDuration = 0.08f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    int32 FixedFrame = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    float OffsetAfterPeakSeconds = 0.06f;

    /** When true, ignore vertical (Z) motion and measure horizontal speed only.
        Useful for RunLoop rules on Hips (locomotion) where jumps should not trigger. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    bool bHorizontalOnly = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    FVector LocationOffset = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    FRotator RotationOffset = FRotator::ZeroRotator;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    FVector Scale = FVector(1.0f);
};

/** Per-rule detection diagnostics, used for threshold calibration and bind reports. */
USTRUCT(BlueprintType)
struct FWorldFlexVFXRuleStats
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    EWorldFlexVFXRuleType RuleType = EWorldFlexVFXRuleType::SpeedTrail;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    FName BoneName = NAME_None;

    /** Threshold the rule actually ran with (cm/s in component space). */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    float UsedThreshold = 0.0f;

    /** Peak component-space speed over the clip, cm/s. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    float MaxSpeed = 0.0f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    float MeanSpeed = 0.0f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    float P90Speed = 0.0f;

    /** Frame index of the peak speed. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    int32 PeakFrame = 0;

    /** Simple starting-point suggestion: midway between mean and max. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    float SuggestedThreshold = 0.0f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    int32 EventCount = 0;

    /** Per-frame component-space speed (cm/s); filled only when curve collection is requested. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "WorldFlex VFX")
    TArray<float> SpeedCurve;
};

USTRUCT(BlueprintType)
struct FWorldFlexVFXEvent
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    EWorldFlexVFXEventType EventType = EWorldFlexVFXEventType::Burst;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    FName BoneName = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    TObjectPtr<UNiagaraSystem> NiagaraSystem = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    int32 Frame = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    float Time = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    float Duration = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    FVector LocationOffset = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    FRotator RotationOffset = FRotator::ZeroRotator;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldFlex VFX")
    FVector Scale = FVector(1.0f);
};

