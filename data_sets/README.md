# data_sets — 随仓库分发的数据快照

本目录用于把 `scripts/export_dataset.sh` 在本机产出的数据快照随 git 仓库一起分发，
免去客户侧 scp 大文件的步骤。

由于 GitHub 单文件 100 MB 硬限制，原始 `dataset.tar.gz`（约 173 MB）被切成 80 MB
分片：

```
data_sets/
├── README.md
├── dataset.tar.gz.sha256       # 原文件 SHA256，用于重组后校验
├── dataset.tar.gz.part_aa      # 80 MB
├── dataset.tar.gz.part_ab      # 80 MB
└── dataset.tar.gz.part_ac      # 余量
```

`data_sets/dataset.tar.gz` 由分片重组得来，已在 `.gitignore` 中排除。

## 客户侧使用

`scripts/bootstrap_data.sh` 已支持把 `--bundle` 指向：

- 单个 tar.gz 文件（传统用法）；
- 一个目录或任意 `dataset.tar.gz.part_*` 文件 → 脚本自动 `cat` 所有 part 还原为 tar.gz，
  并用 `dataset.tar.gz.sha256` 做校验。

因此首部署可以直接：

```bash
sudo bash install.sh --bundle data_sets --bundle-mode safe
# 或显式
sudo bash scripts/bootstrap_data.sh --bundle data_sets --mode safe --restart-service
```

## 重新生成分片（在本机）

```bash
# 1. 生成最新数据 bundle
bash scripts/export_dataset.sh --out data_sets/dataset.tar.gz

# 2. 切片
cd data_sets
rm -f dataset.tar.gz.part_*
split -b 80m dataset.tar.gz dataset.tar.gz.part_

# 3. 校验值
shasum -a 256 dataset.tar.gz > dataset.tar.gz.sha256

# 4. 提交分片
cd ..
git add data_sets/dataset.tar.gz.part_* data_sets/dataset.tar.gz.sha256
git commit -m "chore(data): refresh dataset bundle parts"
git push
```

## 当前快照基本信息

参考 `manifest.json`（重组后位于 tar.gz 内根目录），关键指标：

| 指标 | 数量 |
| --- | --- |
| XHS 机会卡 | ~510 |
| 规则集合 | ~1392 |
| 视觉策略包 | 5 |
| 候选 / Brief | 30 / 11 |
| MediaCrawler XHS jsonl | 8 |

> 客户现场无 LLM key 时直接用快照模式即可启动；如希望从原始 jsonl 重新跑流水线，
> 参考 `docs/CLIENT_DATA_MIGRATION.md` 的 "重建模式" 章节。
