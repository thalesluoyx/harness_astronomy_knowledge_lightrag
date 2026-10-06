# 架构决策记录 (ADR-01)：天文学知识库技术选型

**日期**：2026-10-06  
**状态**：已采纳 (Accepted)  
**决策结论**：采用 **LightRAG** 构建天文学知识库。

---

## 一、 背景与知识库要解决的问题

目前项目已成功将 155 本（原计 164 本包含部分合并或图片册）专业天文学书籍翻译为高质量的中英双语 Markdown 格式，总纯文本语料达到 **153.27 MB**（约 4,000 万 Tokens）。

我们面临的核心挑战是：如何将这庞大的语料转化为一个高可用的大模型知识库。该知识库必须满足以下严格要求：

1. **高级数据挖掘能力（C/D 型需求）**：
   - **C型（全局合成）**：能够跨越 150+ 本书，提炼宏观趋势（如“近 20 年天文摄影技术的演进”）。
   - **D型（多跳推理）**：能够精准追踪细微的逻辑链条（如“通过书A的滤镜原理，结合书B的星云光谱，推理出最佳观测方案”）。
2. **极低的增量更新成本**：天文学知识库需要经常追加新书（如每次追加 3 本）。更新操作必须是日常、廉价且快速的，不能引发全量重算。
3. **适配现有硬件与 API 额度**：在受限环境（本机 AMD Ryzen 7 PRO / 无大显存独立显卡 + 云端 MiniMax Plus 计划每月 6 亿 Token）下，必须保证建库和更新在配额安全线内。

---

## 二、 可选方案与预估成本对比

在给定语料基数（约 40.8M Tokens）和资源约束下，各方案的理论开销评估如下：

| 方案 | 建库 Token 消耗 | 占月配额 (6亿) | 建库预估时间 | 更新 3 本书 (约 3MB) | 增量更新机制 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **微软 GraphRAG** | ~612M Tokens | **102%** ❌ | 数天 | ≈ 需要全量重建 | 极差 |
| **LightRAG** | **~104M Tokens** | **17.3%** ✅ | ~16.5 小时 | 1.9M Tokens (~18分钟) | 原生完美支持 |
| **LazyGraphRAG** | ~0 (仅 Embedding) | 0% ✅ | ~1-2 小时 | ~0 | 原生支持 |
| **HippoRAG v2** | ~20M Tokens | 3.3% ✅ | ~5-8 小时 | ~0.5M Tokens | 原生支持 |

---

## 三、 备选方案的逐一否决原因 (Clear Choice 推演)

### 1. 否决微软官方 GraphRAG
*   **否决原因**：**灾难性的更新时间与 Token 成本**。
*   **详细分析**：GraphRAG 的核心机制是“全局社区聚类与摘要重写”。这意味着每次加入新书，局部图结构的改变都会触发全网社区的重新洗牌。新增 3 本书不仅需要提取新实体，更要求大模型将包含那 150 本旧书在内的全网进行重新总结。其更新时间和成本与首次建库（消耗数天时间和全部月配额）基本持平。这对于动态知识库而言是工程上的死胡同。

### 2. 否决 LazyGraphRAG
*   **否决原因**：**C 型能力（全局合成）的底层缺陷**。
*   **详细分析**：该方案为了省钱，把 LLM 建图推迟到了查询时刻。它严重依赖第一步的普通向量检索（Vector Retrieval）来圈定文本块。面对全局宏观问题，向量检索必定会漏掉大量散落在边缘书籍中的关键信息（由于召回 Top-K 限制）。如果第一步就检索不全，后续临时建构的局部图谱也必然是盲人摸象，无法胜任严肃的数据挖掘工作。

### 3. 否决 HippoRAG v2
*   **否决原因**：**极端偏科，缺乏大局观总结能力**。
*   **详细分析**：HippoRAG v2 使用 Personalized PageRank 算法，在应对 D 型（严密的跨书多跳逻辑推理）问题时是无可争议的王者。但它的机制是“寻找精确链路”，无法生成全局宏观视角。它擅长回答探案级细节，却无法回答“总结全书趋势”这样的 C 型问题，挖掘能力不均衡。

---

## 四、 最终结论

**最终选择：LightRAG (HKUDS)**

**入选理由**：
1. **真正的增量更新**：新增书籍的实体会被优雅地 Upsert 进现有图谱，无需全局重写摘要。更新 3 本书只需消耗 1.9M Token 和十几分钟。
2. **建库成本可控**：首次全量建库仅消耗 104M Token（占 MiniMax Plus 月配额的 17.3%），约 16 小时可完全挂机完成。
3. **最均衡的 C/D 能力**：利用双层检索架构（High-level 主题检索应对 C 型综合，Low-level 实体检索应对 D 型推理），且将图谱的结构信息本身进行了向量化，是目前极少数能同时兼顾局部细节与全局视野的轻量级开源方案。

---

## 五、 附录：全库实测数据规模清册

> **统计基准**：扫描 `bilingual_output` 最终目录  
> **总文件数**：155 本  
> **总体积**：153.27 MB

以下为按语料文件大小（KB）从大到小的完整清单：

| 排名 | 双语版文件名 | 语料大小 (KB) |
|:---|:---|---:|
| 1 | book_68_bilingual.md | 4,521.01 |
| 2 | book_69_bilingual.md | 3,592.29 |
| 3 | book_73_bilingual.md | 2,598.49 |
| 4 | book_The Caldwell Objects (2003)_bilingual.md | 2,401.36 |
| 5 | book_45_bilingual.md | 2,322.69 |
| 6 | book_Hidden Treasures (2007)_bilingual.md | 2,233.71 |
| 7 | book_64_bilingual.md | 2,164.44 |
| 8 | book_23_bilingual.md | 2,015.89 |
| 9 | book_Southern Gems (2013)_bilingual.md | 1,999.01 |
| 10 | book_85_bilingual.md | 1,805.19 |
| 11 | book_143_bilingual.md | 1,803.34 |
| 12 | book_The Secret Deep (2011)_bilingual.md | 1,755.48 |
| 13 | book_97_bilingual.md | 1,729.02 |
| 14 | book_106_bilingual.md | 1,663.85 |
| 15 | book_55_bilingual.md | 1,661.06 |
| 16 | book_118_bilingual.md | 1,641.86 |
| 17 | book_87_bilingual.md | 1,639.08 |
| 18 | book_128_bilingual.md | 1,499.25 |
| 19 | book_77_bilingual.md | 1,479.17 |
| 20 | book_29_bilingual.md | 1,451.23 |
| 21 | book_131_bilingual.md | 1,450.49 |
| 22 | book_53_bilingual.md | 1,445.12 |
| 23 | book_44_bilingual.md | 1,434.02 |
| 24 | book_146_bilingual.md | 1,403.76 |
| 25 | book_9_bilingual.md | 1,355.33 |
| 26 | book_151_bilingual.md | 1,345.09 |
| 27 | book_115_bilingual.md | 1,342.69 |
| 28 | book_158_bilingual.md | 1,342.52 |
| 29 | book_58_bilingual.md | 1,325.11 |
| 30 | book_38_bilingual.md | 1,323.42 |
| 31 | book_56_bilingual.md | 1,277.30 |
| 32 | book_60_bilingual.md | 1,254.12 |
| 33 | book_20_bilingual.md | 1,245.84 |
| 34 | book_35_bilingual.md | 1,240.28 |
| 35 | book_2_bilingual.md | 1,221.39 |
| 36 | book_91_bilingual.md | 1,207.58 |
| 37 | book_4_bilingual.md | 1,204.00 |
| 38 | book_148_bilingual.md | 1,203.53 |
| 39 | book_46_bilingual.md | 1,160.61 |
| 40 | book_90_bilingual.md | 1,140.26 |
| 41 | book_37_bilingual.md | 1,133.18 |
| 42 | book_The Messier Objects (1998)_bilingual.md | 1,111.60 |
| 43 | book_17_bilingual.md | 1,111.29 |
| 44 | book_50_bilingual.md | 1,107.09 |
| 45 | book_121_bilingual.md | 1,099.18 |
| 46 | book_84_bilingual.md | 1,092.17 |
| 47 | book_130_bilingual.md | 1,091.57 |
| 48 | book_32_bilingual.md | 1,059.94 |
| 49 | book_62_bilingual.md | 1,049.83 |
| 50 | book_133_bilingual.md | 1,042.53 |
| 51 | book_99_bilingual.md | 1,040.79 |
| 52 | book_22_bilingual.md | 1,035.65 |
| 53 | book_111_bilingual.md | 1,032.22 |
| 54 | book_98_bilingual.md | 1,025.63 |
| 55 | book_78_bilingual.md | 1,015.78 |
| 56 | book_113_bilingual.md | 1,009.20 |
| 57 | book_39_bilingual.md | 1,004.82 |
| 58 | book_100_bilingual.md | 990.16 |
| 59 | book_31_bilingual.md | 986.94 |
| 60 | book_157_bilingual.md | 976.40 |
| 61 | book_18_bilingual.md | 972.25 |
| 62 | book_7_bilingual.md | 970.71 |
| 63 | book_42_bilingual.md | 969.74 |
| 64 | book_163_bilingual.md | 964.19 |
| 65 | book_51_bilingual.md | 963.72 |
| 66 | book_25_bilingual.md | 962.67 |
| 67 | book_117_bilingual.md | 959.78 |
| 68 | book_8_bilingual.md | 957.69 |
| 69 | book_5_bilingual.md | 952.28 |
| 70 | book_123_bilingual.md | 939.92 |
| 71 | book_11_bilingual.md | 938.58 |
| 72 | book_15_bilingual.md | 936.65 |
| 73 | book_49_bilingual.md | 922.99 |
| 74 | book_86_bilingual.md | 920.09 |
| 75 | book_149_bilingual.md | 918.37 |
| 76 | book_40_bilingual.md | 918.25 |
| 77 | book_96_bilingual.md | 907.22 |
| 78 | book_79_bilingual.md | 894.50 |
| 79 | book_43_bilingual.md | 885.07 |
| 80 | book_67_bilingual.md | 876.29 |
| 81 | book_41_bilingual.md | 874.82 |
| 82 | book_21_bilingual.md | 868.06 |
| 83 | book_57_bilingual.md | 865.30 |
| 84 | book_102_bilingual.md | 858.91 |
| 85 | book_52_bilingual.md | 856.26 |
| 86 | book_136_bilingual.md | 854.52 |
| 87 | book_155_bilingual.md | 847.38 |
| 88 | book_28_bilingual.md | 846.10 |
| 89 | book_124_bilingual.md | 839.11 |
| 90 | book_12_bilingual.md | 838.41 |
| 91 | book_61_bilingual.md | 832.89 |
| 92 | book_1_bilingual.md | 829.94 |
| 93 | book_10_bilingual.md | 822.34 |
| 94 | book_125_bilingual.md | 818.55 |
| 95 | book_76_bilingual.md | 816.72 |
| 96 | book_30_bilingual.md | 814.38 |
| 97 | book_137_bilingual.md | 810.38 |
| 98 | book_81_bilingual.md | 805.88 |
| 99 | book_104_bilingual.md | 802.75 |
| 100 | book_65_bilingual.md | 797.86 |
| 101 | book_24_bilingual.md | 784.46 |
| 102 | book_134_bilingual.md | 781.26 |
| 103 | book_152_bilingual.md | 780.10 |
| 104 | book_75_bilingual.md | 779.19 |
| 105 | book_19_bilingual.md | 775.28 |
| 106 | book_16_bilingual.md | 773.27 |
| 107 | book_112_bilingual.md | 768.17 |
| 108 | book_59_bilingual.md | 764.11 |
| 109 | book_126_bilingual.md | 760.20 |
| 110 | book_129_bilingual.md | 753.75 |
| 111 | book_153_bilingual.md | 750.59 |
| 112 | book_156_bilingual.md | 747.85 |
| 113 | book_92_bilingual.md | 726.19 |
| 114 | book_105_bilingual.md | 719.62 |
| 115 | book_144_bilingual.md | 715.42 |
| 116 | book_34_bilingual.md | 709.58 |
| 117 | book_83_bilingual.md | 703.69 |
| 118 | book_135_bilingual.md | 684.60 |
| 119 | book_33_bilingual.md | 683.26 |
| 120 | book_95_bilingual.md | 677.34 |
| 121 | book_138_bilingual.md | 674.02 |
| 122 | book_36_bilingual.md | 663.30 |
| 123 | book_72_bilingual.md | 654.34 |
| 124 | book_139_bilingual.md | 651.59 |
| 125 | book_94_bilingual.md | 650.59 |
| 126 | book_47_bilingual.md | 636.17 |
| 127 | book_108_bilingual.md | 631.55 |
| 128 | book_103_bilingual.md | 610.98 |
| 129 | book_114_bilingual.md | 605.63 |
| 130 | book_159_bilingual.md | 595.48 |
| 131 | book_141_bilingual.md | 595.46 |
| 132 | book_80_bilingual.md | 595.06 |
| 133 | book_140_bilingual.md | 592.46 |
| 134 | book_162_bilingual.md | 591.66 |
| 135 | book_63_bilingual.md | 590.72 |
| 136 | book_161_bilingual.md | 583.31 |
| 137 | book_27_bilingual.md | 569.27 |
| 138 | book_150_bilingual.md | 566.70 |
| 139 | book_101_bilingual.md | 539.22 |
| 140 | book_109_bilingual.md | 526.49 |
| 141 | book_164_bilingual.md | 522.17 |
| 142 | book_119_bilingual.md | 513.47 |
| 143 | book_122_bilingual.md | 510.54 |
| 144 | book_110_bilingual.md | 462.46 |
| 145 | book_93_bilingual.md | 458.73 |
| 146 | book_54_bilingual.md | 438.79 |
| 147 | book_89_bilingual.md | 428.71 |
| 148 | book_107_bilingual.md | 419.06 |
| 149 | book_160_bilingual.md | 399.92 |
| 150 | book_154_bilingual.md | 398.46 |
| 151 | book_116_bilingual.md | 387.55 |
| 152 | book_66_bilingual.md | 375.03 |
| 153 | book_147_bilingual.md | 271.85 |
| 154 | book_142_bilingual.md | 30.62 |
| 155 | book_127_bilingual.md | 20.68 |
