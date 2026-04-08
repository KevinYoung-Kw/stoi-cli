#!/usr/bin/env python3
"""
STOI GUI Launcher - Apple Design Edition
启动图形界面（Web 界面）
"""

import sys
import argparse


def launch_web():
    """启动 Apple 风格 Web 界面"""
    try:
        from stoi_web_apple import main as web_main
        web_main()
    except ImportError as e:
        print(f"❌ 启动失败: {e}")
        print("请安装 Flask: pip3 install flask")
        sys.exit(1)


def main(args=None):
    """启动 GUI"""
    if args is None:
        args = sys.argv[1:] if len(sys.argv) > 1 else []

    parser = argparse.ArgumentParser(description="💩 STOI GUI (Apple Design)")
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=5000,
        help="端口号 (默认: 5000)"
    )

    parsed_args = parser.parse_args(args)

    print("🎨 启动 STOI - Apple Design Edition")
    print(f"📱 界面风格: 简约、现代、优雅")
    print(f"🌐 访问地址: http://127.0.0.1:{parsed_args.port}")
    print("")

    # 修改端口
    import stoi_web_apple
    import flask

    @flask.copy_current_request_context
    def run_app():
        stoi_web_apple.app.run(
            host='127.0.0.1',
            port=parsed_args.port,
            debug=False
        )

    # 直接调用 main
    import sys
    original_argv = sys.argv
    try:
        sys.argv = ['stoi_web_apple.py']
        launch_web()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    main()
