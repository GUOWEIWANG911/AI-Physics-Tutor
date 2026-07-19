#!/bin/bash

# ================= 配置区 =================
SERVER_USER="acho"
SERVER_HOST="139.196.75.88"
SERVER_DIR="/home/acho/MyAgent"

# 需要同步的文件列表（根据实际路径调整）
FILES=(
    "app/app.py"
    "app/api_server.py"
    "nginx.conf"
    "docker-compose.yml"
)

# ================= 颜色定义 =================
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 开始自动化部署流程...${NC}"

# ================= 1. 上传代码到服务器 =================
echo -e "${YELLOW}📤 正在上传代码到服务器...${NC}"
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        scp "$file" ${SERVER_USER}@${SERVER_HOST}:${SERVER_DIR}/
        echo -e "${GREEN}✅ $file 上传成功${NC}"
    else
        echo -e "${RED}❌ $file 不存在，跳过${NC}"
    fi
done

# ================= 2. 安全清理磁盘空间 =================
echo -e "${YELLOW}🧹 正在安全清理 Docker 无用资源...${NC}"
ssh ${SERVER_USER}@${SERVER_HOST} "
    cd ${SERVER_DIR}
    docker system prune -f
    docker builder prune -f
"
echo -e "${GREEN}✅ 磁盘清理完成（数据卷和运行中镜像已保留）${NC}"

# ================= 3. 重新构建镜像 =================
echo -e "${YELLOW}🔨 正在重新构建 Docker 镜像...${NC}"
ssh ${SERVER_USER}@${SERVER_HOST} "
    cd ${SERVER_DIR}
    docker compose build --no-cache
"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 镜像构建成功${NC}"
else
    echo -e "${RED}❌ 镜像构建失败，请检查服务器日志${NC}"
    exit 1
fi

# ================= 4. 启动服务 =================
echo -e "${YELLOW}⚙️  正在启动 Docker 服务...${NC}"
ssh ${SERVER_USER}@${SERVER_HOST} "
    cd ${SERVER_DIR}
    docker compose up -d
"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 服务启动成功${NC}"
else
    echo -e "${RED}❌ 服务启动失败，请检查服务器日志${NC}"
    exit 1
fi

# ================= 5. 等待后端就绪 =================
echo -e "${YELLOW}⏳ 等待后端模型加载完成（预计3-5分钟）...${NC}"
ssh ${SERVER_USER}@${SERVER_HOST} "
    cd ${SERVER_DIR}
    docker compose logs -f backend
" &
LOG_PID=$!

# 等待10秒让日志开始输出
sleep 10

# 监听日志，检测到就绪信号后自动退出
while true; do
    if ssh ${SERVER_USER}@${SERVER_HOST} "docker compose logs backend 2>/dev/null | grep -q '所有模型加载完毕！系统已就绪。'"; then
        echo -e "${GREEN}✅ 后端模型加载完成，系统已就绪！${NC}"
        kill $LOG_PID 2>/dev/null
        break
    fi
    sleep 5
done

echo -e "${GREEN}🎉 部署完成！请访问 http://${SERVER_HOST}/ 验证${NC}"