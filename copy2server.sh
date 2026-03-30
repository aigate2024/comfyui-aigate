#!/bin/bash

# 本地目录
SRC_DIR="/home/workspace/yizhi/comfyui-aigate"

# 目标服务器信息
REMOTE_PATH="~/comfyui/ComfyUI/custom_nodes"

REMOTE_USER=""
REMOTE_HOST=""
REMOTE_PORT=""
PASSWORD=""

echo "开始部署..."

# 创建临时目录用于打包
TEMP_DIR="/tmp/comfyui-aigate-deploy"
mkdir -p ${TEMP_DIR}/comfyui-aigate

# 复制文件到临时目录的comfyui-aigate子目录，排除vue和svelte目录
rsync -av --exclude='vue/' --exclude='svelte/' --exclude='.git/' --exclude='node_modules/' --exclude='.gitignore' ${SRC_DIR}/ ${TEMP_DIR}/comfyui-aigate/

# 打包压缩
cd ${TEMP_DIR}
tar -czf comfyui-aigate.tar.gz comfyui-aigate

# 创建目标目录（避免scp失败）
ssh -p ${REMOTE_PORT} ${REMOTE_USER}@${REMOTE_HOST} "mkdir -p ${REMOTE_PATH}"

# 传输压缩包到目标服务器
scp -P ${REMOTE_PORT} comfyui-aigate.tar.gz ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/

# 在目标服务器解压并清理
ssh -p ${REMOTE_PORT} ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_PATH} && tar -xzf comfyui-aigate.tar.gz && rm comfyui-aigate.tar.gz"

# 清理临时文件
rm -rf ${TEMP_DIR}

echo "部署完成！"