# 190E x1.5 map: region proposal (Kongming / Zhou Dadudu maps)

Status: **PROPOSAL ONLY**. Nothing in hex/, the kit or the packs was changed. Built 2026-10-01 by `research/main190/proposal_x15/` (run order: km_dots, km_georef, km_polys, han190, commandery_hex, km_rivers, plan_x15, finalize_x15, check_spacing, render_x15, gen_doc).

## Summary

- **240 existing towns + 282 new**: 237 new county towns, 14 new commandery capitals, 31 optional (outside Kongming coverage).

- North of the Yangtze: **236** new; south: **46** (spacing 20 steps north / 26 south, per the commandery's seat).
- **Spacing check (independent all-pairs BFS): 0 pairs involving a new town are closer than 20 steps.** 4 existing 190E pairs are below 20 and are left as they are: Gu Pass–Jiexiu 16; Hulao Pass–Luoyang 19; Anya-guk–Guya-guk 18; Wirye-seong–Michuhol 18.
- Provinces = Han c.190 commanderies: **100** provinces, **39** of them new (`3k_ironic_province_<commandery>`); the rest keep the 190E province key of their capital.
- Estimated region size (walking-Voronoi, hexes): existing median 1227, new median 716, all p10 496 / p90 2251 (vanilla p10 540 / median 1060 / p90 1850).
- Roads: every new town is routed to the network: 282 links, 2714 new road hexes (orange on the sheets).
- Rivers: 36 runs of major Kongming river lie more than 6 hexes from any game river (magenta on the sheets). See the river section below.

Previews: `research/main190/proposal_x15/previews/x15_<sheet>.png` (one per Kongming zhou map + `x15_overview.png`).

## Method and confidence

- **Commanderies** come from Zhou's *China AD 262 (Simple)* map. The flat-fill polygons are flood-filled (155 pieces) and georeferenced on 43 CHGIS seats (quadratic fit, median 3 km residual). Each piece is assigned to the Han commandery whose seat it holds. Post-190 pieces are merged back into their Han parent (longest shared border, plus 27 explicit overrides by historical parentage, e.g. Yidu→Nan, Fuling→Ba, Xinping→You Fufeng). Shang, Wuyuan, Yunzhong, Dingxiang and Shuofang (abandoned by 262) are not on the map, so towns there are spacing-only.
- **Membership is by identity, not position.** An existing town's commandery is the Kongming polygon at its real seat (inventory.csv CHGIS seat); a new town's is its county's. 190E's towns sit a median 28 hexes from where a plain georef puts their seats, and the offset is town-specific, so positions are only used to place new towns.
- **Placement warp:** a piecewise-affine (Delaunay) map anchored on 162 existing towns. 19 towns that 190E reorders were dropped to keep the warp fold-free: Yongshou, Xuantu, Luocheng, Peixian, Juchao, Mengling, Ruyin, Pingyu, Lishi, Jiuquan, Pingyang, Linjing, Julu, Dingzhou, Dongping, Huaixian, Wanling, Jingxing, Guzang. A new town lands where its county sits *relative to the surrounding 190E towns*. Expect ±20 hexes between anchors.
- **Sites** follow the carve6 rules: plain land; no mountain blend, impassable, pass or town; <20% blocked within ~4; the 190E footprint must be off rivers; CAIME sprawl rule. Towns are placed farthest-gap first, preferring Han county seats (CHGIS v5, 943 valid in 190).
- **Unnamed towns** are gap fillers with no unused Han county within 16 hexes, mostly in the frontier (Hexi, Anding, Shuofang, Korea, the Qianwei hills). Each needs a name from you, or can be dropped.

## Decisions needed

1. Naming for the south group: the default is `ironic_south_<commandery>_…`. Keep it, or choose another prefix.
2. Unnamed frontier towns: name each, drop it, or keep it as optional.
3. Optional (off-coverage) candidates `ironic_nomad_spacing_N`: keep or drop.
4. Expansion scenario (below): unlock the padding or not.
5. Existing 190E pairs under 20 steps (passes and Korea): leave them or move them.

## Expansion scenario: unlock the padding (north / west / south-west)

11 commanderies have more than 25% of their mapped land in 190E's non-playable padding (all of it impassable). That land is **already inside the 1338x1053 grid**, so unlocking it needs no grid or extents change and no full downstream rebuild for map size. In the scenario, padding inside these commanderies becomes passable wherever the terrain is not mountain blend; it was evaluated in memory only.

| commandery | new towns, base | new towns, unlocked |
|---|---:|---:|
| dunhuang | 4 | 15 |
| yongchang | 0 | 0 |
| qianwei_sg | 1 | 1 |
| guanghan_sg | 0 | 0 |
| shu | 2 | 2 |
| shu_sg | 0 | 0 |
| juyan | 5 | 5 |
| jiuzhen | 0 | 0 |
| rinan | 0 | 0 |
| yuyang | 2 | 2 |
| shanggu | 0 | 0 |

Total new towns: base 282, unlocked 294 (counts elsewhere shift slightly because the greedy fill runs in a different order). Only Dunhuang (7%) and Yongchang (10%) have land that maps off the grid's west edge; a real west pad (~70 columns) is only worth it if you want Dunhuang's full western reach (Yumen / Yangguan).

## Provinces by zhou

Capital in **bold**. New towns are listed with their proposed key; `*` = new commandery capital.

### Sili

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Hedong | `(keep 190E) 3k_main_hedong` | **Anyi** | Pingyang, Anyi, Puzhou | - |
| Henan | `(keep 190E) 3k_main_luoyang` | **Luoyang** | Luoyang | - |
| Henei | `(keep 190E) 3k_main_henei` | **Huaixian** | Zhixian, Huaixian, Zhaoge, Gongcheng | Linlü `ironic_central_henei_resource_1`<br>Ji `ironic_central_henei_resource_2`<br>(unnamed) `ironic_central_henei_resource_3`<br>(unnamed) `ironic_central_henei_resource_4` |
| Hongnong | `3k_ironic_province_hongnong` | **Hongnong** | Hongnong | Yiyang `ironic_central_hongnong_resource_1` |
| Jingzhao | `(keep 190E) 3k_main_changan` | **Chang'an** | Chang'an, Lantian | - |
| You Fufeng | `3k_ironic_province_fufeng` | **Meixian** | Meixian | Qi `ironic_central_fufeng_resource_1` |
| Zuo Pingyi | `3k_ironic_province_pingyi` | **Gaonu** | Gaonu | (unnamed) `ironic_central_pingyi_resource_1`<br>Linjin `ironic_central_pingyi_resource_2` |

### Yuzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Chen | `3k_ironic_province_chen` | **Chen** | - | Chen* `ironic_central_chen_capital` |
| Liang | `(keep 190E) 3k_main_chenjun` | **Suiyang** | Suiyang | - |
| Lu | `3k_ironic_province_lu` | **Luxian** | Luxian | - |
| Pei | `3k_ironic_province_pei` | **Fuli** | Fuli | Xiang `ironic_central_pei_resource_1`<br>Shansangguo `ironic_central_pei_resource_2`<br>Qiao `ironic_central_pei_resource_3`<br>Xiang `ironic_central_pei_resource_4`<br>Longkang `ironic_central_pei_resource_5` |
| Runan | `(keep 190E) 3k_main_runan` | **Ruyin** | Ruyang, Xiyang, Ruyin, Pingyu | Yangan `ironic_central_runan_resource_1`<br>Xincai `ironic_central_runan_resource_2`<br>Xiyang `ironic_central_runan_resource_3`<br>Pingyu `ironic_central_runan_resource_4`<br>Qisi `ironic_central_runan_resource_5` |
| Yingchuan | `(keep 190E) 3k_main_yingchuan` | **Xuchang** | Liangxian, Xuchang | Zhongmou `ironic_central_yingchuan_resource_1`<br>Yang `ironic_central_yingchuan_resource_2`<br>Dingling `ironic_central_yingchuan_resource_3`<br>Xinji `ironic_central_yingchuan_resource_4` |

### Yanzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Chenliu | `3k_ironic_province_chenliu` | **Chenliu** | Chenliu | Yongqiu `ironic_central_chenliu_resource_1`<br>Jiyang `ironic_central_chenliu_resource_2` |
| Dong | `(keep 190E) 3k_main_dongjun` | **Puyang** | Puyang | Yangping `ironic_central_dong_resource_1` |
| Dongping | `3k_ironic_province_dongping` | **Dongping** | Dongping | Shouzhang `ironic_central_dongping_resource_1` |
| Jibei | `3k_ironic_province_jibei` | **Lu** | - | Lu* `ironic_central_jibei_capital` |
| Jiyin | `3k_ironic_province_jiyin` | **Dingtao** | - | Dingtao* `ironic_central_jiyin_capital`<br>Danfuguo `ironic_central_jiyin_resource_1` |
| Rencheng | `3k_ironic_province_rencheng` | **Rencheng** | - | Rencheng* `ironic_central_rencheng_capital` |
| Shanyang | `3k_ironic_province_shanyang` | **Peixian** | Peixian | - |
| Taishan | `3k_ironic_province_taishan` | **Fenggao** | - | Fenggao* `ironic_central_taishan_capital` |

### Jizhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Anping | `(keep 190E) 3k_main_anping` | **Xindu** | Xindu | Boling `ironic_central_anping_resource_1` |
| Bohai | `(keep 190E) 3k_main_bohai` | **Nanpi** | Nanpi, Zhangwu | Ningjin `ironic_central_bohai_resource_1`<br>Gaochengguo `ironic_central_bohai_resource_2`<br>Xiu `ironic_central_bohai_resource_3` |
| Changshan | `3k_ironic_province_changshan` | **Changshan** | Changshan | (unnamed) `ironic_central_changshan_resource_1`<br>Songzi `ironic_central_changshan_resource_2` |
| Hejian | `3k_ironic_province_hejian` | **Lecheng** | - | Lecheng* `ironic_central_hejian_capital`<br>Dacheng `ironic_central_hejian_resource_1`<br>Mao `ironic_central_hejian_resource_2` |
| Julu | `3k_ironic_province_julu` | **Julu** | Julu | Guanga `ironic_central_julu_resource_1` |
| Qinghe | `3k_ironic_province_qinghe` | **Qinghe** | - | Qinghe* `ironic_central_qinghe_capital` |
| Wei | `(keep 190E) 3k_main_weijun` | **Ye** | Ye | - |
| Zhao | `3k_ironic_province_zhao` | **Shexian** | Shexian | (unnamed) `ironic_central_zhao_resource_1`<br>Pingen `ironic_central_zhao_resource_2` |
| Zhongshan | `(keep 190E) 3k_main_zhongshan` | **Lunu** | Jingxing, Lunu | Hangtang `ironic_central_zhongshan_resource_1` |

### Qingzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Beihai | `(keep 190E) 3k_main_beihai` | **Juxian** | Juxian, Jimo, Dongwu | (unnamed) `ironic_central_beihai_resource_1` |
| Donglai | `(keep 190E) 3k_main_donglai` | **Huangxian** | Huangxian, Changyang, Buji | Changguang `ironic_central_donglai_resource_1` |
| Jinan | `(keep 190E) 3k_main_taishan` | **Dongpingling** | Dongpingling | Zouping `ironic_central_jinan_resource_1` |
| Le'an | `3k_ironic_province_lean` | **Lean** | Lean | - |
| Pingyuan | `(keep 190E) 3k_main_pingyuan` | **Pingyuan** | Pingyuan, Leling | Liaocheng `ironic_central_pingyuan_resource_1` |
| Qi | `3k_ironic_province_qi` | **Linzi** | - | Linzi* `ironic_central_qi_capital` |

### Xuzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Donghai | `(keep 190E) 3k_main_donghai` | **Tanxian** | Farmland, Tanxian | Qu `ironic_central_donghai_resource_1`<br>Licheng `ironic_central_donghai_resource_2`<br>Changlv `ironic_central_donghai_resource_3`<br>Houqiu `ironic_central_donghai_resource_4`<br>(unnamed) `ironic_central_donghai_resource_5` |
| Guangling | `(keep 190E) 3k_main_guangling` | **Huaiyin** | Haixi, Huaiyin, Gaoyou, Jiangdu, Shuxian, Juchao | Ping'an `ironic_central_guangling_resource_1`<br>Yandu `ironic_central_guangling_resource_2`<br>Wan `ironic_central_guangling_resource_3`<br>Songzi `ironic_central_guangling_resource_4`<br>Xiangan `ironic_central_guangling_resource_5`<br>Tangyi `ironic_central_guangling_resource_6`<br>Dongyang `ironic_central_guangling_resource_7`<br>Huaipu `ironic_central_guangling_resource_8`<br>Ling `ironic_central_guangling_resource_9` |
| Langya | `3k_ironic_province_langya` | **Kaiyang** | Kaiyang | Yangdu `ironic_central_langya_resource_1` |
| Pengcheng | `(keep 190E) 3k_main_penchang` | **Pengcheng** | Pengcheng | Lv `ironic_central_pengcheng_resource_1` |
| Xiapi | `(keep 190E) 3k_dlc06_xiapi` | **Xiapi** | Xiapi | Siwuguo `ironic_central_xiapi_resource_1`<br>Quyang `ironic_central_xiapi_resource_2`<br>Xu `ironic_central_xiapi_resource_3`<br>Dongcheng `ironic_central_xiapi_resource_4`<br>Qulu `ironic_central_xiapi_resource_5`<br>Huailing `ironic_central_xiapi_resource_6`<br>Xiaqiu `ironic_central_xiapi_resource_7` |

### Youzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Dai | `(keep 190E) 3k_main_daijun` | **Gaoliu** | Gaoliu | Gaoliu* `ironic_central_dai_resource_1`<br>Pingshu `ironic_central_dai_resource_2` |
| Guangyang | `(keep 190E) 3k_main_youzhou` | **Ji** | Ji, Junmi | - |
| Lelang | `(keep 190E) ironic_region_jinbeongun` | **Daifang** | Nakno-guk, Anya-guk, Mokji-guk, Gori-guk, Geonma-guk, Gaema, Guda, Gungnae-seong, Dongye, Loufang, Seorabeol, Dabeol-guk, Wirye-seong, Michuhol, Uhyumotak-guk, Daifang, Liekou , Changcen , Guya-guk, Geochilsan-guk, Siljik-guk, Haslla | (unnamed) `ironic_central_lelang_resource_1`<br>(unnamed) `ironic_central_lelang_resource_2`<br>(unnamed) `ironic_central_lelang_resource_3`<br>(unnamed) `ironic_central_lelang_resource_4`<br>(unnamed) `ironic_central_lelang_resource_5`<br>(unnamed) `ironic_central_lelang_resource_6`<br>(unnamed) `ironic_central_lelang_resource_7`<br>(unnamed) `ironic_central_lelang_resource_8`<br>(unnamed) `ironic_central_lelang_resource_9`<br>(unnamed) `ironic_central_lelang_resource_10`<br>(unnamed) `ironic_central_lelang_resource_11`<br>(unnamed) `ironic_central_lelang_resource_12` |
| Liaodong | `(keep 190E) 3k_dlc06_liaodong` | **Xiangping** | Xiangping, Pyongyang, Xi'anping | (unnamed) `ironic_central_liaodong_resource_1`<br>(unnamed) `ironic_nomad_spacing_406`<br>(unnamed) `ironic_nomad_spacing_444` |
| Liaodong Dependent State | `3k_ironic_province_liaodong_sg` | **Changli** | Changli | - |
| Liaoxi | `(keep 190E) 3k_main_yu` | **Yangle** | Yangle, Liucheng | - |
| Shanggu | `3k_ironic_province_shanggu` | **Zhuo Lu** | Zhuo Lu | - |
| Xuantu | `(keep 190E) ironic_region_hyunto` | **Hyunto** | Xuantu, Hyunto, Liaodui | - |
| Youbeiping | `(keep 190E) 3k_main_youbeiping` | **Tuyin** | Tuyin, Linyu | - |
| Yuyang | `3k_ironic_province_yuyang` | **Yuyang** | - | Yuyang* `ironic_central_yuyang_capital`<br>Wuqing `ironic_central_yuyang_resource_1` |
| Zhuo | `3k_ironic_province_zhuo` | **Zhuo** | - | Zhuo* `ironic_central_zhuo_capital` |

### Bingzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Shangdang | `(keep 190E) 3k_main_shangdang` | **Zhangzi** | Zhangzi | - |
| Taiyuan | `(keep 190E) 3k_main_taiyuan` | **Jinyang** | Jinyang | Shangai `ironic_central_taiyuan_resource_1` |
| Xihe | `(keep 190E) 3k_main_xihe` | **Lishi** | Jiexiu, Lishi, Mengmen | Zishi `ironic_central_xihe_resource_1`<br>Zhongyang `ironic_central_xihe_resource_2`<br>Lin `ironic_central_xihe_resource_3`<br>Gaolang `ironic_central_xihe_resource_4` |
| Yanmen | `(keep 190E) 3k_main_yanmen` | **Yinguan** | Yinguan, Fanzhi | Banshi `ironic_central_yanmen_resource_1`<br>Yingtao `ironic_central_yanmen_resource_2`<br>Guangwu `ironic_central_yanmen_resource_3`<br>Lvti `ironic_central_yanmen_resource_4` |

### Liangzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Anding | `(keep 190E) 3k_main_anding` | **Linjing** | Linjing, Canluan, Sheyan | (unnamed) `ironic_nomad_spacing_364`<br>(unnamed) `ironic_central_anding_resource_2`<br>(unnamed) `ironic_nomad_spacing_386`<br>(unnamed) `ironic_central_anding_resource_4`<br>(unnamed) `ironic_central_anding_resource_5`<br>(unnamed) `ironic_central_anding_resource_6` |
| Beidi | `3k_ironic_province_beidi` | **Fuping** | - | Fuping* `ironic_central_beidi_capital` |
| Dunhuang | `(keep 190E) ironic_region_hanyang` | **Dunhuang** | Dunhuang | Mingan `ironic_hexi_dunhuang_resource_1`<br>(unnamed) `ironic_hexi_dunhuang_resource_2`<br>(unnamed) `ironic_hexi_dunhuang_resource_3`<br>Xiaogu `ironic_hexi_dunhuang_resource_4` |
| Hanyang | `3k_ironic_province_hanyang` | **Tianshui** | Tianshui, Shanggui | (unnamed) `ironic_central_hanyang_resource_1`<br>(unnamed) `ironic_central_hanyang_resource_2`<br>(unnamed) `ironic_central_hanyang_resource_3`<br>(unnamed) `ironic_central_hanyang_resource_4`<br>(unnamed) `ironic_central_hanyang_resource_5`<br>(unnamed) `ironic_central_hanyang_resource_6`<br>(unnamed) `ironic_central_hanyang_resource_7`<br>(unnamed) `ironic_central_hanyang_resource_8` |
| Jincheng | `(keep 190E) 3k_main_jincheng` | **Jincheng** | Jincheng, Xidu, Nan'an | (unnamed) `ironic_central_jincheng_resource_1` |
| Jiuquan | `3k_ironic_province_jiuquan` | **Jiuquan** | Jiuquan | (unnamed) `ironic_hexi_jiuquan_resource_1`<br>Yanshou `ironic_hexi_jiuquan_resource_2`<br>(unnamed) `ironic_hexi_jiuquan_resource_3`<br>(unnamed) `ironic_hexi_jiuquan_resource_4`<br>(unnamed) `ironic_hexi_jiuquan_resource_5`<br>(unnamed) `ironic_hexi_jiuquan_resource_6`<br>(unnamed) `ironic_hexi_jiuquan_resource_7`<br>(unnamed) `ironic_hexi_jiuquan_resource_8`<br>(unnamed) `ironic_hexi_jiuquan_resource_9`<br>(unnamed) `ironic_hexi_jiuquan_resource_10`<br>(unnamed) `ironic_hexi_jiuquan_resource_11` |
| Longxi | `3k_ironic_province_longxi` | **Didao** | Huandao | Didao* `ironic_central_longxi_capital`<br>Xiangwu `ironic_central_longxi_resource_1` |
| Wudu | `(keep 190E) 3k_main_wudu` | **Xiabian** | Xiabian | - |
| Wuwei | `(keep 190E) 3k_main_wuwei` | **Guzang** | Sanshui, Zhanyin, Guzang, Xiutu, Lingzhou | (unnamed) `ironic_nomad_spacing_319`<br>(unnamed) `ironic_hexi_wuwei_resource_2`<br>(unnamed) `ironic_hexi_wuwei_resource_3`<br>(unnamed) `ironic_nomad_spacing_399`<br>(unnamed) `ironic_nomad_spacing_403`<br>(unnamed) `ironic_hexi_wuwei_resource_6`<br>(unnamed) `ironic_hexi_wuwei_resource_7`<br>(unnamed) `ironic_hexi_wuwei_resource_8`<br>(unnamed) `ironic_hexi_wuwei_resource_9`<br>(unnamed) `ironic_hexi_wuwei_resource_10` |
| Zhangye | `(keep 190E) ironic_region_xi` | **Lude** | Lude | (unnamed) `ironic_hexi_zhangye_resource_1`<br>(unnamed) `ironic_hexi_zhangye_resource_2`<br>Wulan `ironic_hexi_zhangye_resource_3` |
| Zhangye Dependent State | `3k_ironic_province_zhangye_sg` | **Rile** | Rile | (unnamed) `ironic_hexi_zhangye_sg_resource_1`<br>Fanhe `ironic_hexi_zhangye_sg_resource_2`<br>(unnamed) `ironic_hexi_zhangye_sg_resource_3`<br>mei `ironic_hexi_zhangye_sg_resource_4` |
| Zhangye Juyan Dependent State | `(keep 190E) ironic_region_wuyuan` | **Wuyuan** | Wuyuan, Yuan, Xihai | (unnamed) `ironic_hexi_juyan_resource_1`<br>(unnamed) `ironic_nomad_spacing_350`<br>(unnamed) `ironic_hexi_juyan_resource_3`<br>(unnamed) `ironic_hexi_juyan_resource_4`<br>(unnamed) `ironic_hexi_juyan_resource_5` |

### Yizhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Ba | `(keep 190E) 3k_main_bajun` | **Jiangzhou** | Yong'an, Quren, Jiangzhou, Danqu, Langzhong, Hanchang, Fuling, Jianwei, Shanglian | (unnamed) `ironic_central_ba_resource_1`<br>Linjiang `ironic_central_ba_resource_2`<br>(unnamed) `ironic_central_ba_resource_3`<br>Dianjiang `ironic_central_ba_resource_4`<br>Zhi `ironic_central_ba_resource_5`<br>(unnamed) `ironic_central_ba_resource_6`<br>(unnamed) `ironic_central_ba_resource_7`<br>(unnamed) `ironic_central_ba_resource_8` |
| Guanghan | `3k_ironic_province_guanghan` | **Zitong** | Zitong, Luocheng | (unnamed) `ironic_central_guanghan_resource_1`<br>(unnamed) `ironic_central_guanghan_resource_2`<br>(unnamed) `ironic_central_guanghan_resource_3`<br>Xiaming `ironic_central_guanghan_resource_4`<br>郪 `ironic_central_guanghan_resource_5`<br>Fu `ironic_central_guanghan_resource_6`<br>(unnamed) `ironic_central_guanghan_resource_7` |
| Guanghan Dependent State | `3k_ironic_province_guanghan_sg` | **Yinping** | Yinping | - |
| Hanzhong | `(keep 190E) 3k_main_hanzhong` | **Nanzheng** | Nanzheng, Shangyong, Xicheng | - |
| Qianwei | `(keep 190E) 3k_main_jiangyang` | **Jiangyang** | Zizhong, Jiangyang, Wuyang, Zhuti, Pingyi | (unnamed) `ironic_central_qianwei_resource_1`<br>(unnamed) `ironic_central_qianwei_resource_2`<br>Nanguang `ironic_central_qianwei_resource_3`<br>(unnamed) `ironic_central_qianwei_resource_4`<br>Guangdu `ironic_central_qianwei_resource_5`<br>(unnamed) `ironic_central_qianwei_resource_6`<br>(unnamed) `ironic_central_qianwei_resource_7`<br>(unnamed) `ironic_central_qianwei_resource_8`<br>(unnamed) `ironic_central_qianwei_resource_9`<br>Fujie `ironic_central_qianwei_resource_10`<br>(unnamed) `ironic_central_qianwei_resource_11`<br>(unnamed) `ironic_central_qianwei_resource_12` |
| Qianwei Dependent State | `3k_ironic_province_qianwei_sg` | **Hanyuan** | - | Hanyuan* `ironic_central_qianwei_sg_capital` |
| Shu | `(keep 190E) 3k_main_chengdu` | **Chengdu** | Chengdu | Pi `ironic_central_shu_resource_1`<br>Linqiong `ironic_central_shu_resource_2` |
| Shu Dependent State | `3k_ironic_province_shu_sg` | **Hanjia** | Hanjia | - |
| Yizhou (Jianning) | `(keep 190E) 3k_main_jianning` | **Weixian** | Dianchi, Wanwen, Longdong, Qingling, Weixian, Tangao, Xiuyun | Tanfeng `ironic_south_yizhou_c_resource_1`<br>(unnamed) `ironic_south_yizhou_c_resource_2`<br>Wu Dan `ironic_south_yizhou_c_resource_3`<br>(unnamed) `ironic_south_yizhou_c_resource_4`<br>Louwo `ironic_south_yizhou_c_resource_5` |
| Yongchang | `(keep 190E) 3k_dlc06_yongchang` | **Buwei** | Buwei, Yongshou | - |
| Yuexi | `3k_ironic_province_yuexi` | **Yuexi** | Yuexi | (unnamed) `ironic_central_yuexi_resource_1` |
| Zangke | `(keep 190E) 3k_main_zangke` | **Julan** | Julan, Yelang, Wulian | - |

### Jingzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Changsha | `(keep 190E) 3k_main_changsha` | **Linxiang** | Linxiang, Chibi, Lingxian, Chaling | Liandao `ironic_south_changsha_resource_1`<br>(unnamed) `ironic_south_changsha_resource_2`<br>(unnamed) `ironic_south_changsha_resource_3`<br>Yiyang `ironic_south_changsha_resource_4`<br>Ling `ironic_south_changsha_resource_5`<br>Luo `ironic_south_changsha_resource_6`<br>(unnamed) `ironic_south_changsha_resource_7` |
| Guiyang | `3k_ironic_province_guiyang` | **Chenxian** | Chenxian, Nanping | Guiyang `ironic_south_guiyang_resource_1`<br>Han `ironic_south_guiyang_resource_2`<br>(unnamed) `ironic_south_guiyang_resource_3`<br>Leiyang `ironic_south_guiyang_resource_4` |
| Jiangxia | `(keep 190E) 3k_main_jiangxia` | **Xiling** | Xiling, Xunyang | Zhu `ironic_central_jiangxia_resource_1`<br>Zhouling `ironic_central_jiangxia_resource_2`<br>Anlu `ironic_central_jiangxia_resource_3`<br>Anyang `ironic_central_jiangxia_resource_4`<br>(unnamed) `ironic_central_jiangxia_resource_5`<br>(unnamed) `ironic_central_jiangxia_resource_6`<br>(unnamed) `ironic_central_jiangxia_resource_7` |
| Lingling | `(keep 190E) 3k_main_lingling` | **Quanling** | Quanling | Zhaoling `ironic_south_lingling_resource_1`<br>Duliang `ironic_south_lingling_resource_2`<br>Shi'an `ironic_south_lingling_resource_3` |
| Nan | `(keep 190E) 3k_main_jingzhou` | **Jiangling** | Jiangling, Huarong, linju | Dangyang `ironic_central_nan_resource_1`<br>Bian `ironic_central_nan_resource_2`<br>Zuotang `ironic_central_nan_resource_3`<br>(unnamed) `ironic_central_nan_resource_4` |
| Nanyang | `(keep 190E) 3k_main_nanyang` | **Wanxian** | Wanxian, Xinye, Xiangyang | Danshui `ironic_central_nanyang_resource_1`<br>Zan `ironic_central_nanyang_resource_2`<br>Zhangling `ironic_central_nanyang_resource_3`<br>Li `ironic_central_nanyang_resource_4`<br>Rang `ironic_central_nanyang_resource_5`<br>Fuyang `ironic_central_nanyang_resource_6`<br>Caiyang `ironic_central_nanyang_resource_7` |
| Wuling | `(keep 190E) 3k_main_wuling` | **Qianling** | Linyuan, Qianling, Chongxian, Chancheng | Yuanling `ironic_south_wuling_resource_1`<br>Chenyang `ironic_south_wuling_resource_2`<br>(unnamed) `ironic_south_wuling_resource_3` |

### Yangzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Danyang | `(keep 190E) 3k_main_xindu` | **Shixin** | Jianye, Wanling, Shixin, Wuhu | You `ironic_south_danyang_resource_1`<br>Danyang `ironic_south_danyang_resource_2`<br>Jurong `ironic_south_danyang_resource_3` |
| Jiujiang (Huainan) | `(keep 190E) 3k_main_yangzhou` | **Shouchun** | Hefei, Shouchun | Chengde `ironic_central_jiujiang_resource_1`<br>Qunqiu `ironic_central_jiujiang_resource_2` |
| Kuaiji | `(keep 190E) 3k_main_kuaiji` | **Shanyin** | Yongning, Wenma, Jian'an, Jiangle, Jianping, Shanyin, Linhai, Wushang, Dong'an, Shashu, Xin'an | Mao `ironic_south_kuaiji_resource_1`<br>Dongbuhouguan `ironic_south_kuaiji_resource_2`<br>(unnamed) `ironic_south_kuaiji_resource_3`<br>(unnamed) `ironic_south_kuaiji_resource_4`<br>(unnamed) `ironic_south_kuaiji_resource_5` |
| Lujiang | `3k_ironic_province_lujiang` | **Gushi** | Gushi | (unnamed) `ironic_central_lujiang_resource_1`<br>(unnamed) `ironic_central_lujiang_resource_2`<br>Anfeng `ironic_central_lujiang_resource_3`<br>(unnamed) `ironic_central_lujiang_resource_4`<br>(unnamed) `ironic_central_lujiang_resource_5` |
| Wu | `3k_ironic_province_wu` | **Wu** | Wu | Haiyan `ironic_south_wu_resource_1`<br>Wucheng `ironic_south_wu_resource_2`<br>Dantu `ironic_south_wu_resource_3`<br>Fuchun `ironic_south_wu_resource_4` |
| Yuzhang | `(keep 190E) 3k_main_yuzhang` | **Nanchang** | Yudu, Yangdu, Poyang, Haihun, Guangchang, Lean, Nanchang, Jianchang, Geyang | Ai `ironic_south_yuzhang_resource_1`<br>(unnamed) `ironic_south_yuzhang_resource_2`<br>(unnamed) `ironic_south_yuzhang_resource_3`<br>(unnamed) `ironic_south_yuzhang_resource_4` |

### Jiaozhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Cangwu | `(keep 190E) 3k_main_cangwu` | **Guangxin** | Guangxin, Fuchuan, Mengling, Siping | Linhe `ironic_south_cangwu_resource_1` |
| Hepu | `(keep 190E) 3k_main_hepu` | **Hepu** | Anning, Hepu, Xuwen | (unnamed) `ironic_south_hepu_resource_1`<br>(unnamed) `ironic_south_hepu_resource_2` |
| Jiaozhi | `(keep 190E) 3k_main_jiaozhi` | **Longbien** | Longbien, Xisui | - |
| Jiuzhen | `(keep 190E) 3k_dlc06_jiuzhen` | **Xupu** | Xupu | - |
| Nanhai | `(keep 190E) 3k_main_nanhai` | **Panyu** | Panyu, Longchuan, Jieyang | (unnamed) `ironic_south_nanhai_resource_1`<br>(unnamed) `ironic_south_nanhai_resource_2` |
| Rinan | `3k_ironic_province_rinan` | **Rinan** | Rinan | - |
| Yulin | `(keep 190E) 3k_main_yulin` | **Bushan** | Dingzhou, Linchen, Bushan, Tanzhong, Guangyu | (unnamed) `ironic_south_yulin_resource_1`<br>Anguang `ironic_south_yulin_resource_2` |

### Optional (outside Kongming coverage)

`ironic_nomad_spacing_298` (502,108) in 3k_main_hepu_resource_2, `ironic_nomad_spacing_314` (453,833) in 3k_main_anding_resource_1, `ironic_nomad_spacing_319` (316,843) in 3k_main_wuwei_resource_2, `ironic_nomad_spacing_320` (365,865) in 3k_main_anding_resource_3, `ironic_nomad_spacing_330` (453,894) in 3k_main_shoufang_resource_2, `ironic_nomad_spacing_344` (493,841) in 3k_main_shoufang_resource_1, `ironic_nomad_spacing_345` (441,862) in 3k_main_shoufang_resource_1, `ironic_nomad_spacing_350` (302,923) in ironic_region_xi_resource_1, `ironic_nomad_spacing_361` (1088,922) in ironic_region_lelang_resource_1, `ironic_nomad_spacing_364` (395,826) in 3k_main_anding_resource_3, `ironic_nomad_spacing_381` (1217,913) in ironic_region_dongokjeo_capital, `ironic_nomad_spacing_386` (424,832) in 3k_main_shoufang_resource_3, `ironic_nomad_spacing_393` (1217,755) in ironic_region_baekje_resource_2, `ironic_nomad_spacing_399` (344,847) in 3k_main_anding_resource_3, `ironic_nomad_spacing_401` (394,877) in 3k_main_shoufang_resource_2, `ironic_nomad_spacing_403` (297,896) in ironic_region_wuwei_resource_3, `ironic_nomad_spacing_406` (1101,900) in ironic_region_lelang_resource_1, `ironic_nomad_spacing_431` (1191,747) in ironic_region_baekje_resource_2, `ironic_nomad_spacing_444` (1063,923) in ironic_region_lelang_resource_1, `ironic_nomad_spacing_451` (1113,918) in ironic_region_dongokjeo_resource_2, `ironic_nomad_spacing_461` (417,872) in 3k_main_shoufang_resource_2, `ironic_nomad_spacing_465` (470,819) in 3k_main_anding_resource_1, `ironic_nomad_spacing_468` (464,851) in 3k_main_shoufang_resource_1, `ironic_nomad_spacing_469` (383,851) in 3k_main_shoufang_resource_3, `ironic_nomad_spacing_475` (1153,713) in ironic_region_baekje_resource_2, `ironic_nomad_spacing_478` (1218,781) in ironic_region_baekje_resource_1, `ironic_nomad_spacing_479` (1174,780) in ironic_region_hanseong_resource_1, `ironic_nomad_spacing_508` (1251,726) in ironic_region_gyeongju_capital, `ironic_nomad_spacing_513` (455,875) in 3k_main_shoufang_resource_1, `ironic_nomad_spacing_514` (435,883) in 3k_main_shoufang_resource_2, `ironic_nomad_spacing_516` (473,886) in 3k_main_shoufang_resource_1

## Rivers

Major Kongming river runs more than 6 hexes from any game river or sea hex: hex (col,row), size and max offset. Because the warp is ±20 hexes between anchors, check each one against the sheet before proposing a re-route. Most are warp noise near reordered towns; consistent long runs are real course differences.

| hex | hexes | max off |
|---|---:|---:|
| (344,745) | 443 | 30.0 |
| (600,744) | 326 | 24.1 |
| (250,630) | 308 | 31.0 |
| (707,758) | 262 | 20.6 |
| (168,752) | 224 | 28.4 |
| (847,620) | 176 | 17.5 |
| (919,656) | 160 | 16.5 |
| (484,566) | 101 | 13.3 |
| (780,730) | 93 | 33.0 |
| (921,598) | 92 | 11.7 |
| (302,807) | 84 | 20.2 |
| (678,593) | 80 | 29.7 |
| (587,809) | 75 | 18.6 |
| (962,573) | 67 | 14.4 |
| (293,959) | 51 | 62.5 |
| (522,786) | 50 | 8.5 |
| (606,537) | 48 | 19.1 |
| (745,617) | 48 | 12.1 |
| (711,829) | 48 | 12.0 |
| (274,981) | 48 | 78.1 |
| (916,566) | 41 | 21.1 |
| (217,375) | 39 | 17.0 |
| (777,765) | 38 | 13.4 |
| (640,518) | 37 | 14.1 |
| (788,504) | 36 | 10.2 |
| (720,595) | 36 | 10.8 |
| (135,394) | 34 | 24.8 |
| (222,360) | 29 | 13.9 |
| (634,504) | 27 | 9.8 |
| (566,541) | 26 | 13.0 |
| (253,512) | 23 | 9.2 |
| (74,928) | 23 | 121.4 |
| (305,872) | 22 | 32.4 |
| (538,591) | 19 | 7.6 |
| (745,787) | 15 | 20.6 |
| (790,811) | 15 | 15.8 |

## Next step after approval

A regions_carve6-style carve on hex/map.hex using these towns (proper territory growth, footprints, roads written), then regions_db / junctions, the CAIME validator, and the usual build chain. The extents don't change unless the west pad is chosen.