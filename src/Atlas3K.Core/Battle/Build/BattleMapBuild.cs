using System.Reflection;

namespace Atlas3K.Core.Battle.Build;

/// <summary>Run order of a battle build step. Ranges by family: 100-199 map folder and terrain rasters, 200-299 meshes
/// (Build/Meshes), 300-399 bmd and vegetation (Build/Bmd).</summary>
[AttributeUsage(AttributeTargets.Class)]
public sealed class BattleStepOrderAttribute(int order) : Attribute
{
    public int Order { get; } = order;
}

/// <summary>
/// The native battle-map build: runs every <see cref="IBattleBuildStep"/> in this assembly (public, parameterless
/// constructor) in <see cref="BattleStepOrderAttribute"/> order, so a family adds a step by adding a class. Steps can
/// be run on their own (<c>build-battle --only name,...</c>).
/// </summary>
public static class BattleMapBuild
{
    /// <summary>All steps, in run order.</summary>
    public static IReadOnlyList<IBattleBuildStep> Steps() =>
        typeof(IBattleBuildStep).Assembly.GetTypes()
            .Where(t => t is { IsClass: true, IsAbstract: false } && typeof(IBattleBuildStep).IsAssignableFrom(t)
                        && t.GetConstructor(Type.EmptyTypes) is not null)
            .OrderBy(t => t.GetCustomAttribute<BattleStepOrderAttribute>()?.Order ?? 1000).ThenBy(t => t.FullName, StringComparer.Ordinal)
            .Select(t => (IBattleBuildStep)Activator.CreateInstance(t)!)
            .ToList();

    /// <summary>Runs the steps (all, or those named in <paramref name="only"/>); returns the steps that failed.</summary>
    public static List<(string Step, Exception Error)> Run(BattleBuildContext ctx, Action<string> log, IReadOnlyCollection<string>? only = null)
    {
        ctx.EnsureOutDirs();
        var failed = new List<(string, Exception)>();
        foreach (var step in Steps())
        {
            if (only is { Count: > 0 } && !only.Contains(step.Name, StringComparer.OrdinalIgnoreCase)) continue;
            var t0 = System.Diagnostics.Stopwatch.StartNew();
            try
            {
                step.Run(ctx, log);
                log($"{step.Name}: done in {t0.Elapsed.TotalSeconds:0.0}s");
            }
            catch (Exception e)
            {
                log($"{step.Name}: FAILED: {e.Message}");
                failed.Add((step.Name, e));
            }
        }
        return failed;
    }
}
