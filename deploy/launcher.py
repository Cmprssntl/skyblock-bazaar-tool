"""PyInstaller 入口：保持相对导入可用。"""

from skyblock_bazaar.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
