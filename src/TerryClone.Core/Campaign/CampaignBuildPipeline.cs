using System.Collections.Concurrent;

namespace TerryClone.Core.Campaign;

/// <summary>
/// Runs the native replacements for BOB's campaign actions, straight from disk (no pack import between steps).
/// Steps wait only for the dependencies that were selected; independent steps run in parallel.
/// </summary>
public sealed class CampaignBuildPipeline
{
    public sealed record StepOutcome(string Step, string Status, StepResult? Result, IReadOnlyList<string> Problems);

    /// <summary>All steps in BOB's build order.</summary>
    public static IReadOnlyList<ICampaignBuildStep> AllSteps { get; } =
    [
        new RastersStep(),
        new TileListStep(),
        new GlobalMapStep(),
        new GlobalMesh.GlobalMeshStep(),
        new Rivers.RiversStep(),
        new Props.GlobalPropsStep(),
        new CameraHeightmapStep(),
        new Trees.TreesStep(),
        new LookupStep(),
    ];

    /// <summary>Steps that run when none are named: every one that is native.</summary>
    public static IEnumerable<ICampaignBuildStep> NativeSteps => AllSteps.Where(s => s is not PendingStep);

    public static ICampaignBuildStep Find(string name) =>
        AllSteps.FirstOrDefault(s => s.Name.Equals(name, StringComparison.OrdinalIgnoreCase))
        ?? throw new ArgumentException($"Unknown step '{name}'. Steps: {string.Join(", ", AllSteps.Select(s => s.Name))}");

    public IReadOnlyList<StepOutcome> Run(CampaignBuildContext ctx, IEnumerable<string>? stepNames = null)
    {
        var steps = stepNames is null ? NativeSteps.ToList() : stepNames.Select(Find).Distinct().ToList();
        var selected = steps.Select(s => s.Name).ToHashSet();
        var outcomes = new ConcurrentDictionary<string, StepOutcome>();
        var tasks = new Dictionary<string, Task>();

        // AllSteps is in dependency order, so every dependency's task exists before its dependents are created.
        foreach (var step in AllSteps.Where(s => selected.Contains(s.Name)))
        {
            var deps = step.DependsOn.Where(selected.Contains).Select(d => tasks[d]).ToArray();
            tasks[step.Name] = Task.WhenAll(deps).ContinueWith(_ =>
            {
                var failedDeps = step.DependsOn.Where(d => outcomes.TryGetValue(d, out var o) && o.Status != "ok").ToList();
                if (failedDeps.Count > 0)
                {
                    outcomes[step.Name] = new StepOutcome(step.Name, "skipped", null, [$"dependency failed: {string.Join(", ", failedDeps)}"]);
                    return;
                }
                var problems = step.CheckInputs(ctx);
                if (problems.Count > 0)
                {
                    outcomes[step.Name] = new StepOutcome(step.Name, "blocked", null, problems);
                    return;
                }
                try
                {
                    ctx.Log($"[{step.Name}] start");
                    var result = step.Run(new CampaignBuildContext(ctx.Paths, ctx.TargetRoot, m => ctx.Log($"[{step.Name}] {m}"))
                        { AcceptedTileMapIssues = ctx.AcceptedTileMapIssues });
                    outcomes[step.Name] = new StepOutcome(step.Name, "ok", result, []);
                }
                catch (Exception e)
                {
                    outcomes[step.Name] = new StepOutcome(step.Name, "failed", null, [e.Message]);
                }
            }, TaskScheduler.Default);
        }
        Task.WaitAll([.. tasks.Values]);
        return AllSteps.Where(s => outcomes.ContainsKey(s.Name)).Select(s => outcomes[s.Name]).ToList();
    }

    /// <summary>Pre-flight report for every step (what <c>bob_diagnose</c> used to check).</summary>
    public static IReadOnlyList<(string Step, bool Native, IReadOnlyList<string> Problems)> Diagnose(CampaignBuildContext ctx) =>
        AllSteps.Select(s => (s.Name, s is not PendingStep, s.CheckInputs(ctx))).ToList();
}
