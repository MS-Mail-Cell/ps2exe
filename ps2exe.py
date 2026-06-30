import sys
import os
import subprocess
import tempfile
import shutil

STUB = r"""
#include <windows.h>
#include <string>
#include <vector>
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "shlwapi.lib")
#pragma comment(lib, "advapi32.lib")

extern "C" {
extern const unsigned char g_ps1Data[];
extern const size_t g_ps1Size;
}

static std::wstring GetTempPs1() {
    wchar_t t[MAX_PATH];
    GetTempPathW(MAX_PATH, t);
    GUID g; CoCreateGuid(&g);
    wchar_t gs[40]; StringFromGUID2(g, gs, 40);
    return std::wstring(t) + L"ps_" + gs + L".ps1";
}
static bool WriteFileW(const wchar_t* path, const BYTE* data, DWORD sz) {
    HANDLE h = CreateFileW(path, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD wr; bool ok = WriteFile(h, data, sz, &wr, nullptr) && wr == sz;
    CloseHandle(h); return ok;
}
static bool IsAdmin() {
    BOOL a = FALSE; PSID sid = nullptr;
    SID_IDENTIFIER_AUTHORITY auth = SECURITY_NT_AUTHORITY;
    if (AllocateAndInitializeSid(&auth, 2, SECURITY_BUILTIN_DOMAIN_RID, DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0, &sid)) {
        CheckTokenMembership(nullptr, sid, &a); FreeSid(sid);
    } return a;
}
static int Run(const wchar_t* ps1, const wchar_t* args, bool wait) {
    std::wstring cmd = L"powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"";
    cmd += ps1; cmd += L"\"";
    if (args && args[0]) { cmd += L" "; cmd += args; }
    STARTUPINFOW si = { sizeof(si) }; PROCESS_INFORMATION pi = {};
    std::vector<wchar_t> buf(cmd.begin(), cmd.end()); buf.push_back(0);
    if (!CreateProcessW(nullptr, buf.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi)) return -1;
    if (wait) { WaitForSingleObject(pi.hProcess, INFINITE); DWORD ec = 0; GetExitCodeProcess(pi.hProcess, &ec); CloseHandle(pi.hThread); CloseHandle(pi.hProcess); return (int)ec; }
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess); return 0;
}
static bool RelaunchAdmin(const wchar_t* ps1, const wchar_t* args) {
    SHELLEXECUTEINFOW sei = { sizeof(sei) };
    sei.lpVerb = L"runas"; sei.lpFile = L"powershell.exe";
    std::wstring p = L"-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \""; p += ps1; p += L"\"";
    if (args && args[0]) { p += L" "; p += args; }
    sei.lpParameters = p.c_str(); sei.nShow = SW_NORMAL;
    return ShellExecuteExW(&sei);
}
static std::wstring GetArgs() {
    LPWSTR cl = GetCommandLineW(); int n = 0;
    LPWSTR* av = CommandLineToArgvW(cl, &n);
    if (!av || n <= 1) { if (av) LocalFree(av); return L""; }
    std::wstring r;
    for (int i = 1; i < n; ++i) {
        if (i > 1) r += L" ";
        bool sp = wcschr(av[i], L' ') != nullptr;
        if (sp) r += L'"'; r += av[i]; if (sp) r += L'"';
    }
    LocalFree(av); return r;
}
int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int) {
    if (!g_ps1Data || !g_ps1Size) { MessageBoxW(nullptr, L"No script embedded", L"Error", MB_OK | MB_ICONERROR); return 1; }
    std::wstring tmp = GetTempPs1();
    if (!WriteFileW(tmp.c_str(), g_ps1Data, (DWORD)g_ps1Size)) { MessageBoxW(nullptr, L"Failed to extract script", L"Error", MB_OK | MB_ICONERROR); return 1; }
    std::wstring args = GetArgs();
    bool needAdmin = false;
    const char* head = (const char*)g_ps1Data;
    size_t check = g_ps1Size > 4096 ? 4096 : g_ps1Size;
    for (size_t i = 0; i < check - 30; ++i) { if (memcmp(head + i, "#requires -RunAsAdministrator", 29) == 0) { needAdmin = true; break; } }
    int rc;
    if (needAdmin && !IsAdmin()) { RelaunchAdmin(tmp.c_str(), args.c_str()); rc = 0; }
    else { rc = Run(tmp.c_str(), args.c_str(), true); }
    DeleteFileW(tmp.c_str()); return rc;
}
"""

def bin_to_c_array(data, var_name):
    lines = ["#include <stddef.h>", ""]
    lines.append(f"const unsigned char {var_name}[] = {{")
    row = []
    for i, b in enumerate(data):
        row.append(f"0x{b:02x}")
        if len(row) == 16:
            lines.append("    " + ", ".join(row) + ",")
            row = []
    if row:
        lines.append("    " + ", ".join(row) + ",")
    lines[-1] = lines[-1].rstrip(",")
    lines.append("};")
    lines.append(f"const size_t g_ps1Size = {len(data)};")
    return "\n".join(lines)

def find_compiler():
    for name in ["cl.exe", "gcc", "g++"]:
        path = shutil.which(name)
        if path: return name, path
    return None, None

def compile_msvc(src, out, cc_path):
    cmd = [cc_path, "/nologo", "/O2", "/W4", "/GS-", "/MT", "/DUNICODE", "/D_UNICODE",
           "/Fe" + out, src, "shell32.lib", "shlwapi.lib", "advapi32.lib"]
    subprocess.run(cmd, check=True)

def compile_gcc(src, out, cc_path):
    cmd = [cc_path, "-O2", "-s", "-static", "-mwindows", src, "-o", out,
           "-lshell32", "-lshlwapi", "-ladvapi32"]
    subprocess.run(cmd, check=True)

def main():
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <input.ps1> <output.exe>")
        sys.exit(1)
    ps1_path = sys.argv[1]
    out_path = sys.argv[2]
    if not os.path.exists(ps1_path):
        print(f"Error: {ps1_path} not found"); sys.exit(1)
    with open(ps1_path, "rb") as f:
        ps1_data = f.read()
    cc_name, cc_path = find_compiler()
    if not cc_path:
        print("Error: No compiler found. Install MSVC or MinGW.")
        sys.exit(1)
    with tempfile.TemporaryDirectory() as tmp:
        data_cpp = os.path.join(tmp, "data.cpp")
        with open(data_cpp, "w") as f:
            f.write(bin_to_c_array(ps1_data, "g_ps1Data"))
        main_cpp = os.path.join(tmp, "main.cpp")
        with open(main_cpp, "w") as f:
            f.write(STUB)
        if cc_name == "cl.exe":
            compile_msvc(main_cpp, out_path, cc_path)
        else:
            compile_gcc(main_cpp, out_path, cc_path)
    print(f"Built: {out_path}")
    print(f"Embedded: {ps1_path} ({len(ps1_data)} bytes)")

if __name__ == "__main__":
    main()
