#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "OpenWLPlayableCharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UAnimSequence;
class USkeletalMesh;

UCLASS(Blueprintable)
class OPENWLPLAYABLE_API AOpenWLPlayableCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    AOpenWLPlayableCharacter();

    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    virtual void PossessedBy(AController* NewController) override;

    UFUNCTION(BlueprintCallable, Category = "OpenWL|Playable")
    void SetAvatarMesh(USkeletalMesh* InMesh);

    UFUNCTION(BlueprintCallable, Category = "OpenWL|Playable")
    void SetLocomotionAnimations(UAnimSequence* InIdleAnimation, UAnimSequence* InMoveAnimation);

    UFUNCTION(BlueprintCallable, Category = "OpenWL|Playable")
    void SetMovementSpeeds(float InWalkSpeed, float InRunSpeed);

    UFUNCTION(BlueprintCallable, Category = "OpenWL|Playable")
    void PlayIdle();

    UFUNCTION(BlueprintCallable, Category = "OpenWL|Playable")
    void PlayMove();

    UFUNCTION(BlueprintCallable, Category = "OpenWL|Playable")
    bool TriggerSkill(FName SkillName);

protected:
    virtual void BeginPlay() override;

    void MoveForward(float Value);
    void MoveRight(float Value);
    void TurnAtRate(float Rate);
    void LookUpAtRate(float Rate);
    void PressMoveForward();
    void ReleaseMoveForward();
    void PressMoveBackward();
    void ReleaseMoveBackward();
    void PressMoveRight();
    void ReleaseMoveRight();
    void PressMoveLeft();
    void ReleaseMoveLeft();
    void StartSprint();
    void StopSprint();
    void ApplyRawKeyMovement();
    void UpdateLocomotionAnimation();

protected:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "OpenWL|Camera")
    USpringArmComponent* CameraBoom;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "OpenWL|Camera")
    UCameraComponent* FollowCamera;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Animation")
    UAnimSequence* IdleAnimation;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Animation")
    UAnimSequence* MoveAnimation;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Animation")
    UAnimSequence* RunAnimation;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Animation")
    float MoveSpeedThreshold = 5.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Movement")
    float WalkSpeed = 350.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Movement")
    float RunSpeed = 650.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Movement")
    float JumpVelocity = 500.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Movement")
    float GravityScale = 1.6f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Movement")
    float AirControl = 0.35f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Camera")
    float BaseTurnRate = 45.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "OpenWL|Camera")
    float BaseLookUpRate = 45.0f;

private:
    bool bMoveAnimationActive = false;
    bool bIsSprinting = false;
    bool bForwardPressed = false;
    bool bBackwardPressed = false;
    bool bRightPressed = false;
    bool bLeftPressed = false;
};
