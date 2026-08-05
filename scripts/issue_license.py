#!/usr/bin/env python3
"""本地签发离线 License（私钥勿提交、勿打包）。

用法:
  # 生成密钥对到 keys/（默认）
  python scripts/issue_license.py gen-keys

  # 签发一年期
  python scripts/issue_license.py issue \\
    --private-key keys/ed25519_private.key \\
    --customer "某某物业" \\
    --days 365 \\
    --out ~/Desktop/customer.lic

  # 指定到期日
  python scripts/issue_license.py issue \\
    --private-key keys/ed25519_private.key \\
    --customer "某某物业" \\
    --expires 2027-12-31 \\
    --out ~/Desktop/customer.lic

生成新密钥后，请将公钥 Base64 同步写入 app/license.py 的 PUBLIC_KEY_B64。

注意：签发产物仅作分发用，应用不会自动读取 keys/ 下的文件；
用户必须在安装后于应用内「导入授权」。
"""

from __future__ import annotations

import argparse
import base64
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nacl.signing import SigningKey

from app.license import PUBLIC_KEY_B64, build_signed_license


def cmd_gen_keys(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    sk = SigningKey.generate()
    vk = sk.verify_key
    priv = base64.b64encode(bytes(sk)).decode("ascii")
    pub = base64.b64encode(bytes(vk)).decode("ascii")
    priv_path = out_dir / "ed25519_private.key"
    pub_path = out_dir / "ed25519_public.key"
    priv_path.write_text(priv + "\n", encoding="utf-8")
    pub_path.write_text(pub + "\n", encoding="utf-8")
    print(f"私钥: {priv_path}")
    print(f"公钥: {pub_path}")
    print()
    print("请将下列常量写入 app/license.py：")
    print(f'PUBLIC_KEY_B64 = "{pub}"')
    print()
    print("当前应用内嵌公钥为：")
    print(f'PUBLIC_KEY_B64 = "{PUBLIC_KEY_B64}"')


def cmd_issue(args: argparse.Namespace) -> None:
    key_path = Path(args.private_key).expanduser()
    if not key_path.is_file():
        raise SystemExit(f"私钥不存在: {key_path}")
    private_key_b64 = key_path.read_text(encoding="utf-8").strip()
    if args.expires:
        expires_at = date.fromisoformat(args.expires)
    else:
        expires_at = date.today() + timedelta(days=int(args.days))
    text = build_signed_license(
        private_key_b64=private_key_b64,
        customer=args.customer,
        expires_at=expires_at,
        issued_at=date.fromisoformat(args.issued) if args.issued else None,
    )
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"已签发: {out}")
    print(f"客户: {args.customer}")
    print(f"到期: {expires_at.isoformat()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tally 离线 License 签发工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("gen-keys", help="生成 Ed25519 密钥对")
    p_gen.add_argument(
        "--out",
        default=str(ROOT / "keys"),
        help="输出目录（默认 keys/）",
    )

    p_issue = sub.add_parser("issue", help="签发 License 文件")
    p_issue.add_argument(
        "--private-key",
        required=True,
        help="私钥文件路径（Base64 seed）",
    )
    p_issue.add_argument("--customer", required=True, help="客户名称")
    p_issue.add_argument("--days", type=int, default=365, help="有效天数（默认 365）")
    p_issue.add_argument("--expires", default="", help="到期日 YYYY-MM-DD（优先于 --days）")
    p_issue.add_argument("--issued", default="", help="签发日 YYYY-MM-DD（默认今天）")
    p_issue.add_argument("--out", required=True, help="输出 .lic 路径")

    args = parser.parse_args()
    if args.command == "gen-keys":
        cmd_gen_keys(Path(args.out).expanduser())
    elif args.command == "issue":
        cmd_issue(args)
    else:
        parser.error(f"未知命令: {args.command}")


if __name__ == "__main__":
    main()
