#include "OpenWLPlayableCharacter.h"

#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/NameTypes.h"

AOpenWLPlayableCharacter::AOpenWLPlayableCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    AutoPossessPlayer = EAutoReceiveInput::Player0;

    bUseControllerRotationPitch = false;
    bUseControllerRotationYaw = false;
    bUseControllerRotationRoll = false;

    UCharacterMovementComponent* MoveComp = GetCharacterMovement();
    MoveComp->bOrientRotationToMovement = true;
    MoveComp->RotationRate = FRotator(0.0f, 540.0f, 0.0f);
    MoveComp->MaxWalkSpeed = WalkSpeed;
    MoveComp->JumpZVelocity = JumpVelocity;
    MoveComp->GravityScale = GravityScale;
    MoveComp->AirControl = AirControl;
    MoveComp->BrakingDecelerationWalking = 2048.0f;

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->TargetArmLength = 360.0f;
    CameraBoom->bUsePawnControlRotation = true;

    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    FollowCamera->bUsePawnControlRotation = false;

    USkeletalMeshComponent* MeshComp = GetMesh();
    MeshComp->SetRelativeLocation(FVector(0.0f, 0.0f, -88.0f));
    MeshComp->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
}

void AOpenWLPlayableCharacter::BeginPlay()
{
    Super::BeginPlay();

    UE_LOG(LogTemp, Warning, TEXT("[OpenWL] BeginPlay Actor=%s Controller=%s AutoPossess=%d"),
        *GetName(),
        Controller ? *Controller->GetName() : TEXT("None"),
        static_cast<int32>(AutoPossessPlayer));

    UCharacterMovementComponent* MoveComp = GetCharacterMovement();
    MoveComp->MaxWalkSpeed = WalkSpeed;
    MoveComp->JumpZVelocity = JumpVelocity;
    MoveComp->GravityScale = GravityScale;
    MoveComp->AirControl = AirControl;

    if (Controller == nullptr)
    {
        if (APlayerController* PlayerController = UGameplayStatics::GetPlayerController(this, 0))
        {
            UE_LOG(LogTemp, Warning, TEXT("[OpenWL] Forcing Player0 possess: %s"), *PlayerController->GetName());
            PlayerController->Possess(this);
        }
    }

    PlayIdle();
}

void AOpenWLPlayableCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    ApplyRawKeyMovement();
    UpdateLocomotionAnimation();
}

void AOpenWLPlayableCharacter::PossessedBy(AController* NewController)
{
    Super::PossessedBy(NewController);
    UE_LOG(LogTemp, Warning, TEXT("[OpenWL] PossessedBy Actor=%s Controller=%s"),
        *GetName(),
        NewController ? *NewController->GetName() : TEXT("None"));
}

void AOpenWLPlayableCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    UE_LOG(LogTemp, Warning, TEXT("[OpenWL] SetupPlayerInputComponent Actor=%s InputComponent=%s"),
        *GetName(),
        PlayerInputComponent ? *PlayerInputComponent->GetName() : TEXT("None"));

    PlayerInputComponent->BindAxis(TEXT("MoveForward"), this, &AOpenWLPlayableCharacter::MoveForward);
    PlayerInputComponent->BindAxis(TEXT("MoveRight"), this, &AOpenWLPlayableCharacter::MoveRight);
    PlayerInputComponent->BindAxis(TEXT("Turn"), this, &APawn::AddControllerYawInput);
    PlayerInputComponent->BindAxis(TEXT("LookUp"), this, &APawn::AddControllerPitchInput);
    PlayerInputComponent->BindAxis(TEXT("TurnRate"), this, &AOpenWLPlayableCharacter::TurnAtRate);
    PlayerInputComponent->BindAxis(TEXT("LookUpRate"), this, &AOpenWLPlayableCharacter::LookUpAtRate);
    PlayerInputComponent->BindAction(TEXT("Jump"), IE_Pressed, this, &ACharacter::Jump);
    PlayerInputComponent->BindAction(TEXT("Jump"), IE_Released, this, &ACharacter::StopJumping);
    PlayerInputComponent->BindAction(TEXT("Sprint"), IE_Pressed, this, &AOpenWLPlayableCharacter::StartSprint);
    PlayerInputComponent->BindAction(TEXT("Sprint"), IE_Released, this, &AOpenWLPlayableCharacter::StopSprint);

    PlayerInputComponent->BindKey(EKeys::W, IE_Pressed, this, &AOpenWLPlayableCharacter::PressMoveForward);
    PlayerInputComponent->BindKey(EKeys::W, IE_Released, this, &AOpenWLPlayableCharacter::ReleaseMoveForward);
    PlayerInputComponent->BindKey(EKeys::S, IE_Pressed, this, &AOpenWLPlayableCharacter::PressMoveBackward);
    PlayerInputComponent->BindKey(EKeys::S, IE_Released, this, &AOpenWLPlayableCharacter::ReleaseMoveBackward);
    PlayerInputComponent->BindKey(EKeys::D, IE_Pressed, this, &AOpenWLPlayableCharacter::PressMoveRight);
    PlayerInputComponent->BindKey(EKeys::D, IE_Released, this, &AOpenWLPlayableCharacter::ReleaseMoveRight);
    PlayerInputComponent->BindKey(EKeys::A, IE_Pressed, this, &AOpenWLPlayableCharacter::PressMoveLeft);
    PlayerInputComponent->BindKey(EKeys::A, IE_Released, this, &AOpenWLPlayableCharacter::ReleaseMoveLeft);
    PlayerInputComponent->BindKey(EKeys::SpaceBar, IE_Pressed, this, &ACharacter::Jump);
    PlayerInputComponent->BindKey(EKeys::SpaceBar, IE_Released, this, &ACharacter::StopJumping);
    PlayerInputComponent->BindKey(EKeys::LeftShift, IE_Pressed, this, &AOpenWLPlayableCharacter::StartSprint);
    PlayerInputComponent->BindKey(EKeys::LeftShift, IE_Released, this, &AOpenWLPlayableCharacter::StopSprint);
}

void AOpenWLPlayableCharacter::SetAvatarMesh(USkeletalMesh* InMesh)
{
    if (!InMesh)
    {
        return;
    }
    GetMesh()->SetSkeletalMesh(InMesh);
}

void AOpenWLPlayableCharacter::SetLocomotionAnimations(UAnimSequence* InIdleAnimation, UAnimSequence* InMoveAnimation)
{
    IdleAnimation = InIdleAnimation;
    MoveAnimation = InMoveAnimation;
    RunAnimation = InMoveAnimation;
    bMoveAnimationActive = false;
    PlayIdle();
}

void AOpenWLPlayableCharacter::SetMovementSpeeds(float InWalkSpeed, float InRunSpeed)
{
    WalkSpeed = InWalkSpeed;
    RunSpeed = InRunSpeed;
    GetCharacterMovement()->MaxWalkSpeed = bIsSprinting ? RunSpeed : WalkSpeed;
}

void AOpenWLPlayableCharacter::PlayIdle()
{
    if (!IdleAnimation)
    {
        return;
    }
    GetMesh()->PlayAnimation(IdleAnimation, true);
    bMoveAnimationActive = false;
}

void AOpenWLPlayableCharacter::PlayMove()
{
    UAnimSequence* AnimationToPlay = bIsSprinting && RunAnimation ? RunAnimation : MoveAnimation;
    if (!AnimationToPlay)
    {
        return;
    }
    GetMesh()->PlayAnimation(AnimationToPlay, true);
    bMoveAnimationActive = true;
}

bool AOpenWLPlayableCharacter::TriggerSkill(FName SkillName)
{
    UE_LOG(LogTemp, Log, TEXT("[OpenWL] TriggerSkill placeholder: %s"), *SkillName.ToString());
    return false;
}

void AOpenWLPlayableCharacter::MoveForward(float Value)
{
    if (!FMath::IsNearlyZero(Value))
    {
        UE_LOG(LogTemp, Warning, TEXT("[OpenWL] MoveForward Value=%f Controller=%s"),
            Value,
            Controller ? *Controller->GetName() : TEXT("None"));
    }
    if (Controller == nullptr || FMath::IsNearlyZero(Value))
    {
        return;
    }

    const FRotator ControlRotation = Controller->GetControlRotation();
    const FRotator YawRotation(0.0f, ControlRotation.Yaw, 0.0f);
    const FVector Direction = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X);
    AddMovementInput(Direction, Value);
}

void AOpenWLPlayableCharacter::MoveRight(float Value)
{
    if (!FMath::IsNearlyZero(Value))
    {
        UE_LOG(LogTemp, Warning, TEXT("[OpenWL] MoveRight Value=%f Controller=%s"),
            Value,
            Controller ? *Controller->GetName() : TEXT("None"));
    }
    if (Controller == nullptr || FMath::IsNearlyZero(Value))
    {
        return;
    }

    const FRotator ControlRotation = Controller->GetControlRotation();
    const FRotator YawRotation(0.0f, ControlRotation.Yaw, 0.0f);
    const FVector Direction = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y);
    AddMovementInput(Direction, Value);
}

void AOpenWLPlayableCharacter::TurnAtRate(float Rate)
{
    AddControllerYawInput(Rate * BaseTurnRate * GetWorld()->GetDeltaSeconds());
}

void AOpenWLPlayableCharacter::PressMoveForward()
{
    UE_LOG(LogTemp, Warning, TEXT("[OpenWL] W pressed"));
    bForwardPressed = true;
}

void AOpenWLPlayableCharacter::ReleaseMoveForward()
{
    bForwardPressed = false;
}

void AOpenWLPlayableCharacter::PressMoveBackward()
{
    UE_LOG(LogTemp, Warning, TEXT("[OpenWL] S pressed"));
    bBackwardPressed = true;
}

void AOpenWLPlayableCharacter::ReleaseMoveBackward()
{
    bBackwardPressed = false;
}

void AOpenWLPlayableCharacter::PressMoveRight()
{
    UE_LOG(LogTemp, Warning, TEXT("[OpenWL] D pressed"));
    bRightPressed = true;
}

void AOpenWLPlayableCharacter::ReleaseMoveRight()
{
    bRightPressed = false;
}

void AOpenWLPlayableCharacter::PressMoveLeft()
{
    UE_LOG(LogTemp, Warning, TEXT("[OpenWL] A pressed"));
    bLeftPressed = true;
}

void AOpenWLPlayableCharacter::ReleaseMoveLeft()
{
    bLeftPressed = false;
}

void AOpenWLPlayableCharacter::LookUpAtRate(float Rate)
{
    AddControllerPitchInput(Rate * BaseLookUpRate * GetWorld()->GetDeltaSeconds());
}

void AOpenWLPlayableCharacter::StartSprint()
{
    bIsSprinting = true;
    GetCharacterMovement()->MaxWalkSpeed = RunSpeed;
    if (bMoveAnimationActive && RunAnimation && RunAnimation != MoveAnimation)
    {
        PlayMove();
    }
}

void AOpenWLPlayableCharacter::StopSprint()
{
    bIsSprinting = false;
    GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
    if (bMoveAnimationActive && MoveAnimation)
    {
        PlayMove();
    }
}

void AOpenWLPlayableCharacter::ApplyRawKeyMovement()
{
    if (Controller == nullptr)
    {
        return;
    }

    const float ForwardValue = (bForwardPressed ? 1.0f : 0.0f) + (bBackwardPressed ? -1.0f : 0.0f);
    const float RightValue = (bRightPressed ? 1.0f : 0.0f) + (bLeftPressed ? -1.0f : 0.0f);
    if (!FMath::IsNearlyZero(ForwardValue))
    {
        MoveForward(ForwardValue);
    }
    if (!FMath::IsNearlyZero(RightValue))
    {
        MoveRight(RightValue);
    }
}

void AOpenWLPlayableCharacter::UpdateLocomotionAnimation()
{
    const float Speed2D = GetVelocity().Size2D();
    if (Speed2D > MoveSpeedThreshold)
    {
        if (!bMoveAnimationActive)
        {
            PlayMove();
        }
    }
    else if (bMoveAnimationActive)
    {
        PlayIdle();
    }
}
