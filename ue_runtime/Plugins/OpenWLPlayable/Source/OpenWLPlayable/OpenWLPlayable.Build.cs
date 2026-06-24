using UnrealBuildTool;

public class OpenWLPlayable : ModuleRules
{
    public OpenWLPlayable(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "GameplayTasks"
        });

        PrivateDependencyModuleNames.AddRange(new string[] { });
    }
}
