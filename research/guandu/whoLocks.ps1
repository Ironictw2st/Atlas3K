param([string]$Path)
# Lists the processes holding a file open, via the Windows Restart Manager API.
Add-Type @"
using System; using System.Collections.Generic; using System.Runtime.InteropServices;
public static class RstMgr {
  [StructLayout(LayoutKind.Sequential)] struct UNIQUE_PROCESS { public int dwProcessId; public System.Runtime.InteropServices.ComTypes.FILETIME ProcessStartTime; }
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] struct RM_PROCESS_INFO { public UNIQUE_PROCESS Process; [MarshalAs(UnmanagedType.ByValTStr, SizeConst=256)] public string strAppName; [MarshalAs(UnmanagedType.ByValTStr, SizeConst=64)] public string strServiceShortName; public int ApplicationType; public uint AppStatus; public uint TSSessionId; [MarshalAs(UnmanagedType.Bool)] public bool bRestartable; }
  [DllImport("rstrtmgr.dll", CharSet=CharSet.Unicode)] static extern int RmStartSession(out uint h, int f, string key);
  [DllImport("rstrtmgr.dll")] static extern int RmEndSession(uint h);
  [DllImport("rstrtmgr.dll", CharSet=CharSet.Unicode)] static extern int RmRegisterResources(uint h, uint n, string[] files, uint a, UNIQUE_PROCESS[] p, uint s, string[] svc);
  [DllImport("rstrtmgr.dll")] static extern int RmGetList(uint h, out uint needed, ref uint n, [In, Out] RM_PROCESS_INFO[] info, ref uint reasons);
  public static List<string> Who(string path) { var r = new List<string>(); uint h; RmStartSession(out h, 0, Guid.NewGuid().ToString());
    try { RmRegisterResources(h, 1, new[]{path}, 0, null, 0, null); uint need=0, n=0, why=0; RmGetList(h, out need, ref n, null, ref why);
      var info = new RM_PROCESS_INFO[need]; n = need; if (need>0 && RmGetList(h, out need, ref n, info, ref why)==0) foreach (var i in info) r.Add(i.Process.dwProcessId + " " + i.strAppName); }
    finally { RmEndSession(h); } return r; }
}
"@
[RstMgr]::Who($Path)
