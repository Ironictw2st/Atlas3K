namespace Atlas3K.Core.Updates;

/// <summary>A semantic version (major.minor.patch[-prerelease][+build]) ordered as SemVer 2.0 orders them:
/// 0.1.0-alpha.2 &lt; 0.1.0-alpha.10 &lt; 0.1.0-beta.1 &lt; 0.1.0 &lt; 0.1.1. Build metadata is ignored.</summary>
public sealed record SemVersion(int Major, int Minor, int Patch, string Prerelease = "") : IComparable<SemVersion>
{
    public bool IsPrerelease => Prerelease.Length > 0;

    /// <summary>Parses "0.1.0-alpha.2", "v0.1.0-alpha.2" or "0.1.0-alpha.2+abc123"; null when it is not a version.</summary>
    public static SemVersion? TryParse(string? text)
    {
        if (string.IsNullOrWhiteSpace(text)) return null;
        var s = text.Trim();
        if (s[0] is 'v' or 'V') s = s[1..];
        var plus = s.IndexOf('+');
        if (plus >= 0) s = s[..plus];
        var dash = s.IndexOf('-');
        var pre = dash >= 0 ? s[(dash + 1)..] : "";
        var core = (dash >= 0 ? s[..dash] : s).Split('.');
        if (core.Length is < 2 or > 3) return null;
        var nums = new int[3];
        for (var i = 0; i < core.Length; i++)
            if (!int.TryParse(core[i], System.Globalization.NumberStyles.None, System.Globalization.CultureInfo.InvariantCulture, out nums[i])) return null;
        if (dash >= 0 && (pre.Length == 0 || pre.Split('.').Any(p => p.Length == 0))) return null;
        return new SemVersion(nums[0], nums[1], nums[2], pre);
    }

    public static SemVersion Parse(string text) => TryParse(text) ?? throw new FormatException($"'{text}' is not a version");

    public int CompareTo(SemVersion? other)
    {
        if (other is null) return 1;
        var c = Major.CompareTo(other.Major);
        if (c == 0) c = Minor.CompareTo(other.Minor);
        if (c == 0) c = Patch.CompareTo(other.Patch);
        if (c != 0) return c;
        if (!IsPrerelease || !other.IsPrerelease) return other.IsPrerelease.CompareTo(IsPrerelease); // release > prerelease
        var a = Prerelease.Split('.');
        var b = other.Prerelease.Split('.');
        for (var i = 0; i < Math.Min(a.Length, b.Length); i++)
        {
            var an = int.TryParse(a[i], out var ai);
            var bn = int.TryParse(b[i], out var bi);
            c = an && bn ? ai.CompareTo(bi) : an ? -1 : bn ? 1 : string.CompareOrdinal(a[i], b[i]);
            if (c != 0) return c;
        }
        return a.Length.CompareTo(b.Length);
    }

    public static bool operator >(SemVersion a, SemVersion b) => a.CompareTo(b) > 0;
    public static bool operator <(SemVersion a, SemVersion b) => a.CompareTo(b) < 0;
    public static bool operator >=(SemVersion a, SemVersion b) => a.CompareTo(b) >= 0;
    public static bool operator <=(SemVersion a, SemVersion b) => a.CompareTo(b) <= 0;

    public override string ToString() => $"{Major}.{Minor}.{Patch}" + (IsPrerelease ? "-" + Prerelease : "");
}
