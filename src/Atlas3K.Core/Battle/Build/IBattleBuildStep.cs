namespace Atlas3K.Core.Battle.Build;

/// <summary>One step of the native battle-map build (the BOB battle export without BOB). Each step reads the kit sources
/// through <see cref="BattleBuildContext"/> and writes its files under <see cref="BattleBuildContext.OutMapDir"/> /
/// <see cref="BattleBuildContext.OutTileDir"/> / <see cref="BattleBuildContext.OutTileDbDir"/>, in BOB's layout.</summary>
public interface IBattleBuildStep
{
    string Name { get; }
    void Run(BattleBuildContext ctx, Action<string> log);
}
