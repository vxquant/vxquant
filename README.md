# vxquant

#### 介绍
一个简单、易用、面向中国股市实盘的python量化交易框架

#### 模块架构
vxquant 包括以下三个模块:
1. vxquant  -- 量化交易中的标准化组件
2. vxsched  -- 基于事件驱动的调度器实现
3. vxutils  -- 各种常用的python小功能


#### 安装教程

1. 通过 pip 安装

```python
    pip install vxquant
```

2. 通过源代码安装

```shell
    git clone https://gitee.com/vxquant/vxquant && cd  vxquant/
    pip install .
```

#### 使用说明

1.  策略文件目录

```python
# 配置文件存放在 etc/ 目录中
etc/config.json
# 日志文件存放在 log/ 目录中
log/vxquant.log
# 策略文件存放在 mod/ 目录中
mod/
    demo1.py
    demo2.py
    demo3.py

```

2. demo1.py

```python
"""策略demo 1 """

from vxsched import vxengine, vxEvent, vxContext, logger


@vxengine.event_handler("__init__")
def demo1_init(context: vxContext, event: vxEvent) -> None:
    """策略初始化"""
    logger.info(f"title内容: {context.settings.title}")


@vxengine.event_handler("every_tick")
def demo1_every_tick(context: vxContext, event: vxEvent) -> None:
    """每个tick事件触发"""
    logger.info(f"触发时间: {event.type}")

```

3. 运行策略

```shell

python -m vxsched -s worker -c etc/config.json -m mod/

```


#### 参与贡献

1.  Fork 本仓库
2.  新建 Feat_xxx 分支
3.  提交代码
4.  新建 Pull Request



