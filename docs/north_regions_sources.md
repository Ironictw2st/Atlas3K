# Northern regions for the 190E expanded map: candidates and sources

This is a painting guide for the new northern regions: Han commanderies of c. 190 CE that 190E doesn't have yet.
- **Coordinates** are approximate modern positions of the seats (±5 km). Check them against CHGIS (below) when a seat matters.
- **Map positions:** once the warp is final, `research/main190` can turn any lat/lon into a hex with `regions_plan.predict` and draw a marker overlay.

**Already in 190E, north of the Yellow River:**
- **Jizhou:** Wei (Ye), Anping, Zhongshan, Bohai.
- **Youzhou:** Youzhou (Ji / Guangyang), Youbeiping, Dai.
- **Bingzhou:** Taiyuan, Shangdang, Xihe, Yanmen, Shuofang.
- **Qingzhou:** Pingyuan, Beihai, Donglai, Taishan.
- **Northeast:** Liaodong, Yu (Fuyu), and the ironic Korean and Wuyuan regions.

## Jizhou 冀州 (Yuan Shao's base from 191)

| Commandery | Seat (lat, lon) | Other counties worth a region | 190 CE notes |
|---|---|---|---|
| Julu 鉅鹿郡 | Yingtao 廮陶 (37.62, 114.92) | Julu 鉅鹿 (37.22, 115.03), Xiaquyang 下曲陽 (38.03, 115.20) | Zhang Jue's Yellow Turban home commandery |
| Changshan 常山國 | Yuanshi 元氏 (37.77, 114.53) | Zhending 真定 (38.15, 114.57) | Zhao Yun's home (Zhending); Heishan bandits (Zhang Yan) in the western hills |
| Zhao 趙國 | Handan 邯鄲 (36.61, 114.49) | Xiangguo 襄國 (37.07, 114.50) | Only ~30 km north of Ye: at 20-step spacing, a Zhao region should sit at Xiangguo, or be skipped |
| Hejian 河間國 | Lecheng 樂成 (38.19, 116.10) | Gaoyang 高陽 (38.70, 115.78), Mao 鄚 (38.72, 116.07) | Zhang He's home (Mao) |
| Qinghe 清河國 | Ganling 甘陵 (36.93, 115.72) | Dongwucheng 東武城 (37.20, 116.00), Yu 鄃 (36.85, 116.20) | Shared border with Pingyuan and Wei |

## Youzhou 幽州 (Liu Yu at Ji, Gongsun Zan at Beiping)

| Commandery | Seat (lat, lon) | Other counties | 190 CE notes |
|---|---|---|---|
| Zhuo 涿郡 | Zhuo 涿 (39.49, 115.97) | Fanyang 范陽 (39.40, 115.60), Guan 故安 (39.35, 115.45) | Liu Bei's home; Zhang Fei's |
| Shanggu 上谷郡 | Juyong 居庸 (40.47, 115.97) | Zhuolu 涿鹿 (40.38, 115.20), Ning 寧 (40.60, 114.95) | Wuhuan of Shanggu under Nanlou; Xianbei beyond |
| Yuyang 漁陽郡 | Yuyang 漁陽 (40.40, 116.85) | Luxian 潞 (39.90, 116.70), Pinggu 平谷 (40.14, 117.12) | Zhang Chun's rebellion base (187) |
| Liaoxi 遼西郡 | Yangle 陽樂 (41.40, 120.70)* | Linyu 臨渝 (40.00, 119.75), Feiru 肥如 (39.95, 118.80) | Wuhuan under Qiuliju / Tadun |
| Liaodong Shuguo 遼東屬國 | Changli 昌黎 (41.53, 121.24) | Tuhe 徒河 (41.10, 121.10) | Frontier dependency, Wuhuan and Xianbei |

\* Yangle's site is disputed. Tan Qixiang puts it near Yixian; others put it near Qian'an (39.99, 118.70). Pick whichever fits the map.

## Bingzhou 并州 (northern frontier; largely lost to the Xiongnu and Xianbei by 190)

| Commandery | Seat (lat, lon) | Other counties | 190 CE notes |
|---|---|---|---|
| Yunzhong 雲中郡 | Yunzhong 雲中 (40.28, 111.20) | Shanan 沙南 (40.40, 111.60), Xianling 咸陽 (40.65, 111.10) | Abandoned to Xianbei / Southern Xiongnu in the 180s |
| Dingxiang 定襄郡 | Shanwu 善無 (40.20, 112.50) | Wuyuan 武原 (40.40, 112.00) | Same |
| Shang 上郡 | Fushi 膚施 (37.60, 109.70) | Gaonu 高奴 (36.60, 109.50) | Southern Xiongnu / Qiang lands |
| Southern Xiongnu court | Meiji 美稷 (39.70, 111.00) | Later Pingyang area | Yufuluo, then Huchuquan; a "nomad" region that makes sense |

## Qingzhou 青州 / Yanzhou 兗州 (north-east of Dongjun, outside the expanded Central Plains)

| Commandery | Seat (lat, lon) | Other counties | 190 CE notes |
|---|---|---|---|
| Jinan 濟南國 | Dongpingling 東平陵 (36.70, 117.20) | Licheng 歷城 (36.67, 117.02) | Cao Cao was its chancellor (184) |
| Le'an 樂安國 | Linji 臨濟 (37.10, 117.90) | Qiancheng 千乘 (37.20, 118.20) | |
| Qi 齊國 | Linzi 臨淄 (36.87, 118.32) | | Qingzhou's provincial seat |
| Jibei 濟北國 | Lu 盧 (36.40, 116.80) | Gang 剛 (35.90, 116.60) | Bao Xin, Cao Cao's early ally |

## Steppe (optional nomad regions)
- **Xianbei (fragmented after Tanshihuai died in 181):**
  - Kebineng, north of Dai / Shanggu (around 41.0, 114.5);
  - Budugen, north of Yunzhong / Yanmen (around 41.0, 112.0);
  - Suli / Mijia, north of Liaoxi (around 42.0, 120.0).
- **Tanshihuai's old court:** Mount Danhan 彈汗山, near 41.5, 113.5.
- **Wuhuan:** Liucheng 柳城 (41.57, 120.45), Tadun's seat, the Liaoxi Wuhuan base in the 200s.

## Spacing check
The user's rule is that no town may be one army walk from another: 20 walking hex steps (2,450 AP; plains cost 120 per hex). Before you paint, check your seats with `research/main190/spacing.py`.

At 20 steps the Hebei plain fits about 4–5 new towns. Zhao at Handan is too close to Ye. Julu and Qinghe sit between Wei, Anping and Pingyuan, so pick their seats with care.

## Sources
- **Hou Hanshu 後漢書, Treatise on Commanderies and States (郡國志, from Sima Biao's Xu Hanshu):** the authoritative list of Later Han commanderies and counties, c. 140 CE. Online: ctext.org → 後漢書 → 志 → 郡國.
- **Tan Qixiang 譚其驤 (ed.), 中國歷史地圖集 (Historical Atlas of China), vol. 2 (Qin–Han):** the Eastern Han sheets for Jizhou, Youzhou, Bingzhou, Qingzhou and Yanzhou. The standard reference for county sites and borders.
- **CHGIS v6 (China Historical GIS, Harvard / Fudan):** point shapefiles of county seats with lat/lon and valid years. Filter to year 190: https://chgis.fas.harvard.edu (dataverse "CHGIS Version 6").
- **Rafe de Crespigny, *Northern Frontier: The Policies and Strategy of the Later Han Empire* (ANU, 1984):** the Xianbei, Wuhuan and Southern Xiongnu, and the loss of the Bingzhou commanderies. Free PDF at openresearch-repository.anu.edu.au.
- **Rafe de Crespigny, *A Biographical Dictionary of Later Han to the Three Kingdoms* (Brill, 2007):** who held which commandery around 190.
- **Sanguozhi 三國志** and **Zizhi Tongjian 資治通鑑, juan 59–60:** events of 189–191 (Yuan Shao at Bohai and then Ji; Gongsun Zan; Liu Yu).
