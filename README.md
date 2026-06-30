# PS2EXE - PowerShell 脚本编译器

将 PowerShell 脚本 (.ps1) 打包成独立可执行文件 (.exe)。

## 依赖

- Python 3.6+
- C++ 编译器（二选一）：
  - **MSVC**：安装 Visual Studio 或 Build Tools，确保 `cl.exe` 在 PATH
  - **MinGW**：安装 MSYS2 或 MinGW-w64，确保 `gcc` 或 `g++` 在 PATH

## 安装

无需安装，直接下载 `ps2exe.py` 即可使用。

## 用法

### 基础用法

```batch
python ps2exe.py "脚本.ps1" "输出.exe"
```

### 示例

```batch
python ps2exe.py "RemoveWindowsAI.ps1" "RemoveWindowsAI.exe"
```

### 带参数运行

```batch
RemoveWindowsAI.exe -AllOptions -nonInteractive
```

## 工作原理

1. 读取 `.ps1` 文件内容
2. 将脚本数据转换为 C 字节数组
3. 与 C++ 存根代码一起编译
4. 生成单文件 `.exe`

运行时：
1. 从 `.exe` 资源中提取脚本到临时目录
2. 调用 `powershell.exe -ExecutionPolicy Bypass` 执行
3. 执行完毕自动删除临时文件

## 特性

| 特性 | 说明 |
|------|------|
| 单文件 | 无需依赖外部 `.ps1` |
| 参数透传 | 所有命令行参数原样传给 PowerShell |
| 自动提权 | 检测到 `#requires -RunAsAdministrator` 自动 UAC 提权 |
| 无窗口 | 后台静默运行，无 PowerShell 黑窗 |
| 自动清理 | 退出后删除临时脚本 |

## 常见问题

**Q: 编译失败，提示找不到编译器？**

A: 确保 `cl.exe` (MSVC) 或 `gcc`/`g++` (MinGW) 已在系统 PATH 中。

**Q: 生成的 exe 被杀毒软件报毒？**

A: 这是误报。程序本身只是提取并执行 PowerShell，无恶意行为。可添加信任或自行编译。

**Q: 如何查看执行输出？**

A: 当前版本为无窗口模式。如需调试，修改存根代码中的 `-WindowStyle Hidden` 为 `-WindowStyle Normal`。

**Q: 脚本需要管理员权限？**

A: 在 `.ps1` 文件第一行添加 `#requires -RunAsAdministrator`，编译后运行会自动弹出 UAC。

## 文件说明

| 文件 | 说明 |
|------|------|
| `ps2exe.py` | 主打包工具 |
| `stub.cpp` | C++ 存根源码（供参考，打包时自动生成） |

## 许可证

MIT
