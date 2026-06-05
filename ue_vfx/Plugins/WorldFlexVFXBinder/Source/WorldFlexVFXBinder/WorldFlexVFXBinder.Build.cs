using UnrealBuildTool;

public class WorldFlexVFXBinder : ModuleRules
{
    public WorldFlexVFXBinder(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "Niagara",
            "NiagaraAnimNotifies"
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "UnrealEd",
            "AnimationBlueprintLibrary",
            "AssetTools",
            "EditorScriptingUtilities",
            "Json",
            "Projects",
            "Slate",
            "SlateCore"
        });
    }
}
