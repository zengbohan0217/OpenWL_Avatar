#pragma once

#include "Commandlets/Commandlet.h"
#include "WorldFlexVFXBindCommandlet.generated.h"

UCLASS()
class UWorldFlexVFXBindCommandlet : public UCommandlet
{
    GENERATED_BODY()

public:
    UWorldFlexVFXBindCommandlet();

    virtual int32 Main(const FString& Params) override;
};

