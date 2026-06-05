#pragma once

#include "Modules/ModuleManager.h"

class FWorldFlexVFXBinderModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
};

