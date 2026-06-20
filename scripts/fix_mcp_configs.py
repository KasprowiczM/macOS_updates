#!/usr/bin/env python3
import json
import os
import shutil
import sys

def fix_mcp_config(config_path):
    if not os.path.exists(config_path):
        print(f"File not found: {config_path}")
        return False

    print(f"Processing: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return False

    modified = False
    
    if "mcpServers" not in data:
        print("No mcpServers found in config.")
        return False

    # Define paths dynamically — prefer the native toolchain managed by update_npm_cli.sh
    toolchain_home = os.environ.get(
        "MAC_UPDATE_TOOLCHAIN_HOME",
        os.path.expanduser("~/.local/share/mac-update"),
    )
    n_prefix = os.environ.get("N_PREFIX", os.path.join(toolchain_home, "node"))
    npm_global_bin = os.path.join(toolchain_home, "npm-global", "bin")
    bun_bin = os.path.join(
        os.environ.get("BUN_INSTALL", os.path.expanduser("~/.bun")),
        "bin",
    )

    NPX_PATH = os.environ.get("MAC_UPDATE_NPX_PATH") or shutil.which("npx") or os.path.join(n_prefix, "bin", "npx")
    NODE_PATH = os.environ.get("MAC_UPDATE_NODE_PATH") or shutil.which("node") or os.path.join(n_prefix, "bin", "node")

    path_parts = []
    for prefix in [
        npm_global_bin,
        os.path.join(n_prefix, "bin"),
        bun_bin,
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]:
        if prefix and prefix not in path_parts:
            path_parts.append(prefix)
    GLOBAL_PATH = ":".join(path_parts)

    for server_name, server_config in data["mcpServers"].items():
        # 1. Fix command
        cmd = server_config.get("command", "")
        if cmd == "npx" or (cmd.endswith("/npx") and cmd != NPX_PATH):
            server_config["command"] = NPX_PATH
            modified = True
        elif cmd == "node" or (cmd.endswith("/node") and cmd != NODE_PATH):
            server_config["command"] = NODE_PATH
            modified = True
            
        # 2. Fix env PATH
        if "env" not in server_config:
            server_config["env"] = {}
        
        env = server_config["env"]
        current_path = env.get("PATH", "")
        
        if "/opt/homebrew/bin" not in current_path:
            if current_path:
                env["PATH"] = f"{GLOBAL_PATH}:{current_path}"
            else:
                env["PATH"] = GLOBAL_PATH
            modified = True

    if modified:
        try:
            # Create backup before modifying
            bak_path = config_path + '.bak'
            shutil.copy2(config_path, bak_path)
            # Atomic write: tmp file + os.replace
            tmp_path = config_path + f'.tmp.{os.getpid()}'
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
                f.write('\n')
            os.replace(tmp_path, config_path)
            print(f"Successfully updated: {config_path}")
            return True
        except Exception as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            print(f"Error writing JSON: {e}")
            return False
    else:
        print(f"No changes needed for: {config_path}")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fix_mcp_configs.py <path_to_mcp_config.json>")
        sys.exit(1)
    
    success = True
    for path in sys.argv[1:]:
        if not fix_mcp_config(path):
            success = False
            
    sys.exit(0 if success else 1)
