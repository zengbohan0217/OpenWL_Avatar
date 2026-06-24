#pragma once

#include "Modules/ModuleManager.h"

class FOpenWLPlayableModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
};
