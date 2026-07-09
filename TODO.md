## 工作目标：打通pipeline parallel和flashcomm两个特性的叠加

步骤：
1. 学习flashcomm原理，（1）怎么开启开关（2）代码实现原理（3）自己跑一些模型来观测
2. 学习pp并行原理，（1）怎么开启开关（2）代码实现原理（3）自己跑一些模型来观测，有问题拉pp负责人王子岳
3. 尝试打通pp+flashcomm两者的叠加，优先用agent搞
4. 在打通功能前提下，进行性能测试，摸测两者叠加的性能收益场景和特性甜点区

输出件：
1. 输出特性叠加设计文档，原理文档
2. 输出特性叠加使用文档
3. 输出使用agent进行特性叠加开发的最佳实践手册


## 学习资料
1. https://onebox.huawei.com/v/9c563df663d368a03a152f0c1591695e/list
2. "C:\Users\x50063850\AppData\Roaming\WeLink_Desktop\appdata\IM\x50063850\DownloadFiles\vLLM整体架构&多进程管理&进程间通信介绍.pptx"
3. flashcomm基础讲解：https://3ms.huawei.com/km/groups/3225441/blogs/details/22322494
4. pipline parallel基础介绍与配置文档：https://clouddocs.huawei.com/wapp/share/04a6e850-6d2b-495c-ac99-0cda2ea72b10 / pipeline parallel特性负责人：王子岳 00957216

## 机器资源
在LLM组机器协调群公告里有入口

## 
我的电脑上开发
拉到绿区，然后在绿区服务器跑服务、验证
验证结果再回到蓝区。