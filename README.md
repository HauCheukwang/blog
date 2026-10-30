#  Cheukwang Hau's Blog

基于 **Hexo 8** + **Volantis 6.8.3** 主题构建，部署在 **GitHub Pages**（项目页）：

> 线上地址：<https://haucheukwang.github.io/blog/>

- 作者：**Cheukwang Hau**（GitHub：[@HauCheukwang](https://github.com/HauCheukwang)）
- 头像：使用 GitHub 头像 `https://github.com/HauCheukwang.png`
- 仓库：`HauCheukwang/blog`（源码在 `main` 分支，构建产物在 `gh-pages` 分支）

---

## 一、本仓库就是“全盘备份”

本仓库包含博客的**全部源码**，任何人或 Agent 克隆后即可完整重建站点：

| 路径 | 说明 |
|------|------|
| `_config.yml` | Hexo 站点配置（主题、作者、URL、语言等） |
| `themes/volantis/` | Volantis 主题（已扁平 vendored，非子模块，全部进库） |
| `source/` | 博文（`source/_posts/`）、页面（`about`、`friends` 等）、主题覆盖配置（`source/_data/volantis.yml`） |
| `scaffolds/` | 文章/页面模板 |
| `scripts/` | 站点级 Hexo 脚本（含 `sync_via_api.py` 同步工具） |
| `.github/workflows/deploy.yml` | GitHub Pages 自动部署工作流 |
| `package.json` | 依赖声明（Hexo 及必要渲染器/生成器） |
| `yarn.lock` | 锁文件（仅供参考） |

> ⚠️ 以下内容**不入库**（均为可重建的生成物/依赖），靠下面命令还原：
> `node_modules/`（依赖）、`public/`（构建产物）、`db.json`（缓存）、`.deploy/`。

---

## 二、本地环境要求

- **Node.js ≥ 18**（GitHub Actions 使用 22）
- **Git**（标准发布方式需要；受限环境可用 API 方式，见第六节）

## 三、本地安装与预览

```bash
git clone https://github.com/HauCheukwang/blog.git
cd blog
npm install                 # 安装 Hexo 及主题所需依赖
npx hexo server             # 本地预览，访问 http://localhost:4000/blog/
```

## 四、撰写 / 更新博文

```bash
npx hexo new "文章标题"      # 生成 source/_posts/文章标题.md
# 用编辑器写 Markdown 正文
npx hexo generate           # 本地构建，检查无误
```

## 五、部署原理（自动）

- `main` 分支存放**源码**；`.github/workflows/deploy.yml` 在每次 push 到 `main` 时：
  1. `checkout` 源码 → 2. 装 Node 22 → 3. `npm install` → 4. `npx hexo generate` → 5. 用 `peaceiris/actions-gh-pages` 把 `public/` 推送到 `gh-pages` 分支（自动写入 `.nojekyll`）。
- 仓库 Pages 采用 **legacy 分支部署**（发布源 = `gh-pages` 分支），因此由 `gh-pages` 分支自动发布站点。
- 使用仓库自带的 `GITHUB_TOKEN`，**无需配置任何 Secret**。
- 因此：**“更新一次博文 → 推送一次 main → 站点自动重新部署”** 已闭环。

## 六、发布与备份（两种推送方式）

### 方式 A：标准 Git（普通机器可直连 GitHub）

```bash
git add -A
git commit -m "更新博文：xxx"
git push origin main
```

推送后 Actions 自动重建并部署，完成“更新博文即更新站点 + 仓库备份”。

### 方式 B：API 同步（git push 不可达的环境，例如本沙箱）

当环境到 `github.com:443` 的 git 协议超时、无法 `git push` 时，用本仓库自带的脚本把
`git ls-files`（遵循 `.gitignore`）的**全部文件全量镜像**到 `main`：

```bash
GITHUB_TOKEN=ghp_xxx python3 scripts/sync_via_api.py --message "更新博文：xxx"
```

脚本行为：

- 把本地跟踪文件逐一创建 blob → 建 tree → 建 commit → 更新 `main` 引用；
- 远端 `main` 上“仅远端存在”的文件会被删除，**保证 远端 == 本地（全盘备份）**；
- 推送后同样触发 Actions 自动部署。

> 注：脚本以本地为源（source of truth），会覆盖 `main` 的全量内容。若有人在网页端直接改过
> `main` 而本地没有，那些改动会被覆盖。

## 七、CDN / 静态资源说明

Volantis 主题的 `replace` 机制（`themes/volantis/_config.yml`）会把主题默认的
`cdn.jsdelivr.net` 静态资源替换为镜像源，加速加载。

- **当前（2026-10-29 起）配置**：恢复为 Volantis 默认——`cdn.jsdelivr.net/npm` 与
  `cdn.jsdelivr.net/gh` 统一替换为 `unpkg.com`，`dns_prefetch` 指向 `unpkg.com`。
- **2026-10-29 已撤销**：此前把 `unpkg.com` 改为 `gcore.jsdelivr.net/npm` 镜像、并把
  `dns_prefetch` 指向 gcore 的方案，以及配套的 `scripts/replace-assets.js` 脚本，均已回退/删除。
- **关于主题内置的 `gcore.jsdelivr.net/gh/...` 图片地址**：这些是 Volantis 主题**自带的默认**
  图片资源（首页 banner、表情、社交图标等），从首次提交起就存在，属于“原状”的一部分；它们使用
  `gcore.jsdelivr.net/gh/`（而非 `cdn.jsdelivr.net`），不经过上面的 `replace` 规则。
  若你希望连这些也换成 `cdn.jsdelivr.net/gh/` 或 `unpkg`，可另行调整主题 `_config.yml` 与
  `_data/icons.yml` 中的硬编码 URL，改完推送即可。

如需重新启用国内镜像加速，可自行改回 `replace` 规则或换用其它镜像，然后按第六节推送。

## 八、迁移 / 给另一位 Agent 的指引

1. `git clone https://github.com/HauCheukwang/blog.git`（或下载 ZIP）。
2. `cd blog && npm install && npx hexo generate` —— 即可得到与线上一致的站点。
3. 本仓库即完整备份；`scripts/sync_via_api.py` 可在任意环境把本地改动同步上库（无需 `git push`）。
4. 本地预览：`npx hexo server`，访问 `http://localhost:4000/blog/`。

## 九、变更记录（Changelog / 批注）

| 日期 | 提交 / 动作 | 批注 |
|------|-------------|------|
| 初始 | `8e3d393` Initial commit | Hexo + Volantis 主题初始化；含 Volantis 默认 `replace`（cdn.jsdelivr.net→unpkg）及主题内置 `gcore.jsdelivr.net/gh/` 图片默认地址 |
| 早期 | `3f6af22` | 作者名暂设为 Eric（后已改为 Cheukwang Hau） |
| 早期 | `3a30307` | 部署从 Cloudflare Pages 切换到 GitHub Pages（官方 actions/deploy-pages） |
| 早期 | `6415aba` | 作者改名 Cheukwang Hau，GitHub 链接改为 HauCheukwang，头像用 GitHub 头像 |
| 早期 | `5c5e742` | 项目页配置：`root: /blog/`，对应仓库 HauCheukwang/blog |
| 2026-10 | `d1c3a7b` | **曾**把 CDN 改为 gcore.jsdelivr.net 镜像（`replace` 改 unpkg→gcore/npm、dns_prefetch 改 gcore、新增 `scripts/replace-assets.js`） |
| 2026-10-29 | 本次提交 | **撤销**上述 jsDelivr 镜像方案：恢复 `replace` 为 Volantis 默认（cdn.jsdelivr.net→unpkg）、`dns_prefetch` 恢复 unpkg、删除 `scripts/replace-assets.js`；补依赖 `hexo-generator-json-content`；新增 `scripts/sync_via_api.py` 与 `README.md`；把全部源码首次推送到 `main` 分支做全盘备份 |


