# yuque_transfer_cross_space
#### 跨空间转移语雀文档，并维持原有结构

### 背景
原团队文档于几年前使用语雀文档空间存放，某天开始，空间限制在10个人，想要超过10个人，当前空间每人 200/年。  
且文档无法转移出当前空间。  
实属恶心，原本的文档都无法挪动。  
所以写个脚本，把所有文档包括目的从独立空间挪回到个人空间。

### 环境 
python3

```
pip3 install httpx requests simplejson
```

### 使用
参数：  
```
source_url: 来源空间的知识库的链接
target_url: 目的空间的知识库的链接
cookie: 填写 cookie中的 _yuque_session

```

运行: python3 yuque.transfer_cross_space.py
