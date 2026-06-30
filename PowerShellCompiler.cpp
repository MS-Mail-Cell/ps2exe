#include <windows.h>
#include <string>
#include <vector>
#include <fstream>
#include <shlwapi.h>
#pragma comment(lib, "shlwapi.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "advapi32.lib")

static std::wstring ToWide(const char* s) {
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, nullptr, 0);
    std::wstring r(n - 1, 0);
    MultiByteToWideChar(CP_UTF8, 0, s, -1, &r[0], n);
    return r;
}

static std::string ToUTF8(const wchar_t* s) {
    int n = WideCharToMultiByte(CP_UTF8, 0, s, -1, nullptr, 0, nullptr, nullptr);
    std::string r(n - 1, 0);
    WideCharToMultiByte(CP_UTF8, 0, s, -1, &r[0], n, nullptr, nullptr);
    return r;
}

static std::wstring GetTempPs1() {
    wchar_t t[MAX_PATH];
    GetTempPathW(MAX_PATH, t);
    GUID g;
    CoCreateGuid(&g);
    wchar_t gs[40];
    StringFromGUID2(g, gs, 40);
    return std::wstring(t) + L"ps_" + gs + L".ps1";
}

static bool ReadFile(const wchar_t* path, std::vector<BYTE>& out) {
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr,
        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD sz = GetFileSize(h, nullptr);
    out.resize(sz);
    DWORD rd;
    bool ok = ReadFile(h, out.data(), sz, &rd, nullptr) && rd == sz;
    CloseHandle(h);
    return ok;
}

static bool WriteFile(const wchar_t* path, const BYTE* data, DWORD sz) {
    HANDLE h = CreateFileW(path, GENERIC_WRITE, 0, nullptr,
        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD wr;
    bool ok = WriteFile(h, data, sz, &wr, nullptr) && wr == sz;
    CloseHandle(h);
    return ok;
}

static bool IsAdmin() {
    BOOL a = FALSE;
    PSID sid = nullptr;
    SID_IDENTIFIER_AUTHORITY auth = SECURITY_NT_AUTHORITY;
    if (AllocateAndInitializeSid(&auth, 2, SECURITY_BUILTIN_DOMAIN_RID,
        DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0, &sid)) {
        CheckTokenMembership(nullptr, sid, &a);
        FreeSid(sid);
    }
    return a;
}

static int Run(const wchar_t* ps1, const wchar_t* args, bool wait) {
    std::wstring cmd = L"powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"";
    cmd += ps1;
    cmd += L"\"";
    if (args && args[0]) {
        cmd += L" ";
        cmd += args;
    }
    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi = {};
    std::vector<wchar_t> buf(cmd.begin(), cmd.end());
    buf.push_back(0);
    if (!CreateProcessW(nullptr, buf.data(), nullptr, nullptr, FALSE,
        CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi)) return -1;
    if (wait) {
        WaitForSingleObject(pi.hProcess, INFINITE);
        DWORD ec = 0;
        GetExitCodeProcess(pi.hProcess, &ec);
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);
        return (int)ec;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 0;
}

static bool RelaunchAdmin(const wchar_t* ps1, const wchar_t* args) {
    SHELLEXECUTEINFOW sei = { sizeof(sei) };
    sei.lpVerb = L"runas";
    sei.lpFile = L"powershell.exe";
    std::wstring p = L"-NoProfile -ExecutionPolicy Bypass -File \"";
    p += ps1;
    p += L"\"";
    if (args && args[0]) { p += L" "; p += args; }
    sei.lpParameters = p.c_str();
    sei.nShow = SW_NORMAL;
    return ShellExecuteExW(&sei);
}

static std::wstring GetArgs() {
    LPWSTR cl = GetCommandLineW();
    int n = 0;
    LPWSTR* av = CommandLineToArgvW(cl, &n);
    if (!av || n <= 2) { if (av) LocalFree(av); return L""; }
    std::wstring r;
    for (int i = 2; i < n; ++i) {
        if (i > 2) r += L" ";
        bool sp = wcschr(av[i], L' ') != nullptr;
        if (sp) r += L'"';
        r += av[i];
        if (sp) r += L'"';
    }
    LocalFree(av);
    return r;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int) {
    LPWSTR* av;
    int ac;
    av = CommandLineToArgvW(GetCommandLineW(), &ac);
    if (!av || ac < 2) {
        MessageBoxW(nullptr, L"Usage: PowerShellCompiler.exe <script.ps1> [args...]",
            L"Error", MB_OK | MB_ICONERROR);
        if (av) LocalFree(av);
        return 1;
    }
    std::wstring src = av[1];
    LocalFree(av);

    std::vector<BYTE> data;
    if (!ReadFile(src.c_str(), data)) {
        MessageBoxW(nullptr, (L"Cannot read: " + src).c_str(), L"Error", MB_OK | MB_ICONERROR);
        return 1;
    }

    std::wstring tmp = GetTempPs1();
    if (!WriteFile(tmp.c_str(), data.data(), (DWORD)data.size())) {
        MessageBoxW(nullptr, L"Failed to write temp script", L"Error", MB_OK | MB_ICONERROR);
        return 1;
    }

    std::wstring args = GetArgs();
    bool needAdmin = false;
    std::string head((char*)data.data(), data.size() > 4096 ? 4096 : data.size());
    if (head.find("#requires -RunAsAdministrator") != std::string::npos) needAdmin = true;

    int rc;
    if (needAdmin && !IsAdmin()) {
        RelaunchAdmin(tmp.c_str(), args.c_str());
        rc = 0;
    } else {
        rc = Run(tmp.c_str(), args.c_str(), true);
    }

    DeleteFileW(tmp.c_str());
    return rc;
}
