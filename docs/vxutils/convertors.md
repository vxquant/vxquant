## 转换器工具 vxutils/convertors.py


### 1. 日期转换函数: to_timestamp, to_timestring, to_datetime, to_date

>
> python 日期时间格式分为4种形式
>
* timestamps -- 时间戳格式，float类型，表示当前时间距离'1970-01-01 00:00:00'的秒数
  
* timestring -- 时间字符串格式, str类型， 如：'2022-01-01 10:30:31.237595'
  
* datetime   -- python 日期格式, datetime类型, 如: datetime(2022,01,01,10,30,31) 

* struct_time -- time struct, struct_time类型, 如: time.struct_time(tm_year=2022, tm_mon=01, tm_mday=01, tm_hour=10, tm_min=30, tm_sec=31, tm_wday=2, tm_yday=10, tm_isdst=0)

#### (1) to_timestamp(value)  转换为timestamp格式

#### (2) to_timestring(value, fmt='%Y-%m-%d %H:%M:%S.%F')  转换为文本格式时间格式

#### (3) to_datetime(value)  转换为datetime格式,此处格式中，加上本地时区的datetime格式.

### 2. 文本格式和二进制文本转换 to_binary, to_text

#### (1) to_binary(value, encoding='utf-8')   转换为binary格式

#### (2) to_text(value, encoding='utf-8')  转换为text格式

```code
print(to_text(b'text'))
# "text"

print(to_binary("text"))
# b"text"

```

### 3. 转换成枚举类 : to_enum

#### to_enum()