# vxQuant —— 一个简单易用的量化交易工具箱



## 一、安装教程

1.通过pip 安装

```python
pip install vxquant
```

2.通过源码编译

```python
git clone https://github.com/vxquant/vxquant.git
cd vxquant/
python3 setup.py install
```

## 二、模块介绍

当前版本主要包括以下几个主要模块:

### 1. scheduler --- 调度器 负责量化交易过程中对于各个类型时间的处理

#### 1.1 event类 ---事件类

```python
vxEvent:
    # 消息id
    id: uuid
    # 消息通道，主要是用于标识消息的来源
    channel: str 
    # 消息类型，如: on_tick, on_order_status ...
    type: str 
    # 消息内容
    data: Any 
    # 定时触发器，即：一个定时触发，或者循环出发的时间
    trigger: Optional[vxTrigger] 
    # 下次触发事件 通过定义vxTrigger类来确定next_trigger_dt
    next_trigger_dt: timestamp
    # 优先级, 
    # next_trigger_dt越早越快触发，next_trigger_dt相同时prority越小越优先
    priority: int = vxIntField(10)

```

#### vxTrigger类

* vxOnceTrigger ---> 仅触发一次的trigger
  * 参数: run_time 触发时间
  
* vxIntervalTrigger ---> 间隔触发器
  * 参数: start_dt ---> 开始时间
  * 参数: end_dt ---> 结束时间
  * 参数: interval ---> 间隔秒数

* vxDailyTrigger  ---> 每隔interval日的run_time时间执行
  * 参数: run_time --->每天的运行时间,如："09:30:00"
  * 参数: interval --->间隔天数，最少为1天
  * 参数: skip_holiday ---> 是否跳过假日，假日定义可以通过vxtime.is_holiday()判断，通过vxtime.add_holiday() 增加对应的假日

* vxWeeklyTrigger ---> 每周执行
  * 参数: weekday ---> 星期几，0 表示周日，6表示周六
  * 参数: run_time
  * 参数: interval
  * 参数: skip_holiday
  

## 软件架构
软件架构说明


## 安装教程

python setup.py build install
