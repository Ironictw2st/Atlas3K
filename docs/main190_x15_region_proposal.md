# 190E x1.5 map: region proposal (Kongming / Zhou Dadudu maps)

Status: **PROPOSAL ONLY**. Nothing in hex/, the kit or the packs was changed. Built 2026-10-01 by `research/main190/proposal_x15/` (run order: km_dots, km_georef, km_polys, han190, commandery_hex, km_rivers, plan_x15, finalize_x15, check_spacing, render_x15, gen_doc).

## Summary

- **240 existing towns + 68 new**: 55 new county towns, 13 new commandery capitals, 0 optional (outside Kongming coverage).
- **Final selection (user, 2026-10-01): important regions only.** Core = 27 (Han commandery capitals with no town, plus counties that were commandery seats on the AD 262 map); fill = 41 named Han counties chosen greedily while a gap of >= 30 walking steps remained. Unnamed gap fillers and off-coverage candidates are not proposed (they are in the _full doc). No original 190E region is removed or moved.
- North of the Yangtze: **47** new; south: **21** (spacing 20 steps north / 26 south, per the commandery's seat).
- **Spacing check (independent all-pairs BFS): 0 pairs involving a new town are closer than 20 steps.** 4 existing 190E pairs are below 20 and are left as they are: Gu Pass–Jiexiu 16; Hulao Pass–Luoyang 19; Anya-guk–Guya-guk 18; Wirye-seong–Michuhol 18.
- Provinces = Han c.190 commanderies: **98** provinces, **40** of them new (`3k_ironic_province_<commandery>`); the rest keep the 190E province key of their capital.
- Estimated region size (walking-Voronoi, hexes): existing median 1854, new median 1086, all p10 684 / p90 3907 (vanilla p10 540 / median 1060 / p90 1850).
- Roads: every new town is routed to the network: 68 links, 486 new road hexes (orange on the sheets).
- Rivers: 36 runs of major Kongming river lie more than 6 hexes from any game river (magenta on the sheets). See the river section below.

Previews: `research/main190/proposal_x15/previews/x15_<sheet>.png` (one per Kongming zhou map + `x15_overview.png`).

## Method and confidence

- **Commanderies** come from Zhou's *China AD 262 (Simple)* map. The flat-fill polygons are flood-filled (155 pieces) and georeferenced on 43 CHGIS seats (quadratic fit, median 3 km residual). Each piece is assigned to the Han commandery whose seat it holds. Post-190 pieces are merged back into their Han parent (longest shared border, plus 27 explicit overrides by historical parentage, e.g. Yidu→Nan, Fuling→Ba, Xinping→You Fufeng). Shang, Wuyuan, Yunzhong, Dingxiang and Shuofang (abandoned by 262) are not on the map, so towns there are spacing-only.
- **Membership is by identity, not position.** An existing town's commandery is the Kongming polygon at its real seat (inventory.csv CHGIS seat); a new town's is its county's. 190E's towns sit a median 28 hexes from where a plain georef puts their seats, and the offset is town-specific, so positions are only used to place new towns.
- **Placement warp:** a piecewise-affine (Delaunay) map anchored on 162 existing towns. 19 towns that 190E reorders were dropped to keep the warp fold-free: Yongshou, Xuantu, Luocheng, Peixian, Juchao, Mengling, Ruyin, Pingyu, Lishi, Jiuquan, Pingyang, Linjing, Julu, Dingzhou, Dongping, Huaixian, Wanling, Jingxing, Guzang. A new town lands where its county sits *relative to the surrounding 190E towns*. Expect ±20 hexes between anchors.
- **Sites** follow the carve6 rules: plain land; no mountain blend, impassable, pass or town; <20% blocked within ~4; the 190E footprint must be off rivers; CAIME sprawl rule. Towns are placed farthest-gap first, preferring Han county seats (CHGIS v5, 943 valid in 190).
- **Unnamed towns** are gap fillers with no unused Han county within 16 hexes, mostly in the frontier (Hexi, Anding, Shuofang, Korea, the Qianwei hills). Each needs a name from you, or can be dropped.

## Decisions (user, 2026-10-01)

- `ironic_south_` prefix: OK.
- The 105 unnamed towns stay optional (not proposed); only important regions are added.
- Towns outside the Kongming maps: dropped. Border land: stays locked (no expansion).
- The 4 existing 190E pairs under 20 steps: left alone.
- Core + fill at 30 steps. Original regions are kept; moving one is allowed if needed (none needed here).

## Your 11 region rules

| rule | status | detail |
|---|---|---|
| 1_spacing | PASS | 0 new-town pairs < 20 steps; existing 190E pairs left alone: 4 |
| 2_connected | PASS | all members share the capital's landmass (islands exempt) |
| 3_unique_names | PASS | {'clash_with_existing': [], 'duplicate_new': [], 'rule': 'on a clash, rename the OLD region'} |
| 4_prefixes | PASS | all ironic_central_/hexi_/south_ (south approved 2026-10-01) |
| 5_natural_borders | at carve | PENDING carve: the previews are a walking-Voronoi estimate; the carve uses carve6's Dijkstra cost field (ridges, rivers, noise, no straight bisectors) |
| 6_importance | PASS | {'missing': [], 'counts': {'high': 16, 'low': 42, 'medium': 10}, 'note': 'where importance is stored in the game data is still to be confirmed with the user'} |
| 7_passes | PASS | {'size_vs_1x': {'Gu Pass': [89, 89], 'Hangu Pass': [107, 107], 'Hulao Pass': [77, 77], 'Jiameng Pass': [60, 60], 'Kui Pass': [114, 114], 'Qi Pass': [83, 83], 'San Pass': [135, 135], 'Tong Pass': [183, 183], 'Wu Pass': [114, 114]}, 'over': {}, 'note': 'gate passes capped at their 1x (stock 190E) hex  |
| 8_trees | at carve | PENDING carve: tree_clear.py around new footprints and the new roads |
| 9_roads | PASS | {'new_towns_joined_to_network': 68, 'new_towns_not_joined': [], 'note': "every new town's road reaches an existing town; the network as a whole is validated by CAIME's roads check at carve time (this raster model doesn't join Yellow River bridges)"} |
| 10_sites | PASS | no new site inside props / mountains; blocked share < 20% within ~4 hexes |
| 11_zhou_maps | PASS | provinces = Han commanderies from Zhou's maps (Kongming = the same maps as docs/reference/provinces, higher resolution); post-190 splits merged back per the user's earlier choice |
| 12_one_piece | PASS | every new region is one connected piece (islands exempt); estimate defragmented in finalize |

## Hexi corridor (proposal)

- **West pad 140 columns** (grid 1478x1053). That is a map-size change, so the extents rule applies (playable / campaign_maps / camera max x in kit + pack before BOB, then the full chain), and every startpos x shifts by the pad.
- Corridor at 2.6 km/hex (core ~2.0, i.e. ~1.3x compressed), anchored on Guzang. Its shape comes from Zhou's Liangzhou commandery polygons: a strip ~32 hexes north of the Qilian front, the Juyan spur up the Ruo river with its lakes, and the desert bay between Juyan and Wuwei.
- 19641 corridor hexes; Qilian wall (impassable) 7921; 37369 hexes of the old Hexi block become desert (non-playable); lakes 1521 hexes (Dunhuang, Yuanquan, Juyan).
- Spans in hexes: Guzang-Lude 84, Lude-Jiuquan 73, Jiuquan-Dunhuang 129, Lude-Xihai 129 (Guzang-Lude was 30).
- Moved 190E towns (old -> new hex, padded grid): Dunhuang (227, 894) -> (56,934); Jiuquan (288, 943) -> (194,918); Lude (320, 866) -> (264,886); Xihai (419, 946) -> (287,1004); Rile (408, 905) -> (287,872); Xidu (271, 762) -> (311,793); Dayun (247, 814) -> (270,780); Hequ (240, 752) -> (299,770).
- Fill: Yuanquan (Han county in a 61-step gap). Guzang, Xiutu, Jincheng and Qinghai (Xidu, Huandao, Nan'an) are unchanged.
- Spacing inside Hexi: 0 pairs under 20 steps. Proposed road hexes: 630.
- Previews: `previews/hexi_x15_before.png` / `hexi_x15_after.png`.

## Provinces by zhou

Capital in **bold**. New towns are listed with their proposed key; `*` = new commandery capital.

### Sili

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Hedong | `(keep 190E) 3k_main_hedong` | **Anyi** | Pingyang, Anyi, Puzhou | - |
| Henan | `(keep 190E) 3k_main_luoyang` | **Luoyang** | Luoyang | Guandu `ironic_central_henan_resource_1`<br>Gucheng (fill) `ironic_central_henan_resource_2` |
| Henei | `(keep 190E) 3k_main_henei` | **Huaixian** | Zhixian, Huaixian, Zhaoge, Gongcheng | Linlü (fill) `ironic_central_henei_resource_1` |
| Hongnong | `3k_ironic_province_hongnong` | **Hongnong** | Hongnong | - |
| Jingzhao | `(keep 190E) 3k_main_changan` | **Chang'an** | Chang'an, Lantian | - |
| You Fufeng | `3k_ironic_province_fufeng` | **Meixian** | Meixian | Qi `ironic_central_fufeng_resource_1` |

### Yuzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Chen | `3k_ironic_province_chen` | **Chen** | - | Chen* `ironic_central_chen_capital` |
| Liang | `(keep 190E) 3k_main_chenjun` | **Suiyang** | Suiyang | - |
| Lu | `3k_ironic_province_lu` | **Luxian** | Luxian | - |
| Pei | `3k_ironic_province_pei` | **Fuli** | Fuli | Qiao `ironic_central_pei_resource_1` |
| Runan | `(keep 190E) 3k_main_runan` | **Ruyin** | Ruyang, Xiyang, Ruyin, Pingyu | Ancheng `ironic_central_runan_resource_1` |
| Yingchuan | `(keep 190E) 3k_main_yingchuan` | **Xuchang** | Liangxian, Xuchang | Dingling (fill) `ironic_central_yingchuan_resource_1` |

### Yanzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Chenliu | `3k_ironic_province_chenliu` | **Chenliu** | Chenliu | Yu (fill) `ironic_central_chenliu_resource_1` |
| Dong | `(keep 190E) 3k_main_dongjun` | **Puyang** | Puyang | - |
| Dongping | `3k_ironic_province_dongping` | **Dongping** | Dongping | - |
| Jibei | `3k_ironic_province_jibei` | **Lu** | - | Lu* `ironic_central_jibei_capital` |
| Jiyin | `3k_ironic_province_jiyin` | **Dingtao** | - | Dingtao* `ironic_central_jiyin_capital` |
| Rencheng | `3k_ironic_province_rencheng` | **Rencheng** | - | Rencheng* `ironic_central_rencheng_capital` |
| Shanyang | `3k_ironic_province_shanyang` | **Peixian** | Peixian | - |
| Taishan | `3k_ironic_province_taishan` | **Fenggao** | - | Fenggao* `ironic_central_taishan_capital` |

### Jizhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Anping | `(keep 190E) 3k_main_anping` | **Xindu** | Xindu | - |
| Bohai | `(keep 190E) 3k_main_bohai` | **Nanpi** | Nanpi, Zhangwu | - |
| Changshan | `3k_ironic_province_changshan` | **Changshan** | Changshan | - |
| Hejian | `3k_ironic_province_hejian` | **Lecheng** | - | Lecheng* `ironic_central_hejian_capital` |
| Julu | `3k_ironic_province_julu` | **Julu** | Julu | - |
| Qinghe | `3k_ironic_province_qinghe` | **Qinghe** | - | Qinghe* `ironic_central_qinghe_capital` |
| Wei | `(keep 190E) 3k_main_weijun` | **Ye** | Ye | - |
| Zhao | `3k_ironic_province_zhao` | **Shexian** | Shexian | - |
| Zhongshan | `(keep 190E) 3k_main_zhongshan` | **Lunu** | Jingxing, Lunu | - |

### Qingzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Beihai | `(keep 190E) 3k_main_beihai` | **Juxian** | Juxian, Jimo, Dongwu | - |
| Donglai | `(keep 190E) 3k_main_donglai` | **Huangxian** | Huangxian, Changyang, Buji | - |
| Jinan | `(keep 190E) 3k_main_taishan` | **Dongpingling** | Dongpingling | - |
| Le'an | `3k_ironic_province_lean` | **Lean** | Lean | - |
| Pingyuan | `(keep 190E) 3k_main_pingyuan` | **Pingyuan** | Pingyuan, Leling | - |
| Qi | `3k_ironic_province_qi` | **Linzi** | - | Linzi* `ironic_central_qi_capital` |

### Xuzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Donghai | `(keep 190E) 3k_main_donghai` | **Tanxian** | Tanxian | Qu (fill) `ironic_central_donghai_resource_1`<br>Licheng (fill) `ironic_central_donghai_resource_2` |
| Guangling | `(keep 190E) 3k_main_guangling` | **Huaiyin** | Haixi, Huaiyin, Gaoyou, Jiangdu | Wan `ironic_central_guangling_resource_1`<br>Tangyi (fill) `ironic_central_guangling_resource_2` |
| Langya | `3k_ironic_province_langya` | **Kaiyang** | Kaiyang | - |
| Pengcheng | `(keep 190E) 3k_main_penchang` | **Pengcheng** | Pengcheng | - |
| Xiapi | `(keep 190E) 3k_dlc06_xiapi` | **Xiapi** | Xiapi | Siwuguo (fill) `ironic_central_xiapi_resource_1`<br>Xu (fill) `ironic_central_xiapi_resource_2`<br>Qulu (fill) `ironic_central_xiapi_resource_3`<br>Dongcheng (fill) `ironic_central_xiapi_resource_4` |

### Youzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Dai | `(keep 190E) 3k_main_daijun` | **Gaoliu** | Gaoliu | - |
| Guangyang | `(keep 190E) 3k_main_youzhou` | **Ji** | Ji, Junmi | - |
| Liaodong | `(keep 190E) 3k_dlc06_liaodong` | **Xiangping** | Xiangping | - |
| Liaodong Dependent State | `3k_ironic_province_liaodong_sg` | **Changli** | Changli | - |
| Liaoxi | `(keep 190E) 3k_main_yu` | **Yangle** | Yangle, Liucheng | - |
| Shanggu | `3k_ironic_province_shanggu` | **Zhuo Lu** | Zhuo Lu | - |
| Xuantu | `3k_ironic_province_xuantu` | **Xuantu** | Xuantu | - |
| Youbeiping | `(keep 190E) 3k_main_youbeiping` | **Tuyin** | Tuyin, Linyu | - |
| Yuyang | `3k_ironic_province_yuyang` | **Yuyang** | - | Yuyang* `ironic_central_yuyang_capital` |
| Zhuo | `3k_ironic_province_zhuo` | **Zhuo** | - | Zhuo* `ironic_central_zhuo_capital` |

### Bingzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Shangdang | `(keep 190E) 3k_main_shangdang` | **Zhangzi** | Zhangzi | - |
| Taiyuan | `(keep 190E) 3k_main_taiyuan` | **Jinyang** | Jinyang | - |
| Xihe | `(keep 190E) 3k_main_xihe` | **Lishi** | Jiexiu, Lishi, Mengmen | - |
| Yanmen | `(keep 190E) 3k_main_yanmen` | **Yinguan** | Yinguan, Fanzhi | Yingtao (fill) `ironic_central_yanmen_resource_1`<br>Guangwu `ironic_central_yanmen_resource_2` |

### Liangzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Anding | `(keep 190E) 3k_main_anding` | **Linjing** | Linjing, Canluan | - |
| Beidi | `3k_ironic_province_beidi` | **Fuping** | - | Fuping* `ironic_central_beidi_capital` |
| Dunhuang | `(keep 190E) ironic_region_hanyang` | **Dunhuang** | Dunhuang | Yuanquan (fill) `ironic_hexi_dunhuang_resource_1`<br>Mingan (fill) `ironic_hexi_dunhuang_resource_2` |
| Hanyang | `3k_ironic_province_hanyang` | **Tianshui** | Tianshui, Shanggui | - |
| Jincheng | `(keep 190E) 3k_main_jincheng` | **Jincheng** | Jincheng, Xidu | - |
| Jiuquan | `3k_ironic_province_jiuquan` | **Jiuquan** | Jiuquan | Yanshou (fill) `ironic_hexi_jiuquan_resource_1` |
| Longxi | `3k_ironic_province_longxi` | **Didao** | - | Didao* `ironic_central_longxi_capital`<br>Xiangwu (fill) `ironic_central_longxi_resource_1` |
| Wudu | `(keep 190E) 3k_main_wudu` | **Xiabian** | Xiabian | - |
| Wuwei | `(keep 190E) 3k_main_wuwei` | **Guzang** | Zhanyin, Guzang, Xiutu | - |
| Zhangye | `(keep 190E) ironic_region_xi` | **Lude** | Lude | - |
| Zhangye Dependent State | `3k_ironic_province_zhangye_sg` | **Rile** | Rile | - |
| Zhangye Juyan Dependent State | `3k_ironic_province_juyan` | **Xihai** | Xihai | - |

### Yizhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Ba | `(keep 190E) 3k_main_bajun` | **Jiangzhou** | Jiangzhou, Danqu, Langzhong | Linjiang (fill) `ironic_central_ba_resource_1`<br>Zhi (fill) `ironic_central_ba_resource_2`<br>Dianjiang (fill) `ironic_central_ba_resource_3` |
| Guanghan | `3k_ironic_province_guanghan` | **Zitong** | Zitong, Luocheng | Qi (Guanghan) `ironic_central_guanghan_resource_1` |
| Guanghan Dependent State | `3k_ironic_province_guanghan_sg` | **Yinping** | Yinping | - |
| Hanzhong | `(keep 190E) 3k_main_hanzhong` | **Nanzheng** | Nanzheng, Xicheng | - |
| Qianwei | `(keep 190E) 3k_main_jiangyang` | **Jiangyang** | Zizhong, Jiangyang, Wuyang | - |
| Qianwei Dependent State | `3k_ironic_province_qianwei_sg` | **Hanyuan** | - | Hanyuan* `ironic_central_qianwei_sg_capital` |
| Shu | `(keep 190E) 3k_main_chengdu` | **Chengdu** | Chengdu | - |
| Shu Dependent State | `3k_ironic_province_shu_sg` | **Hanjia** | Hanjia | - |
| Yizhou (Jianning) | `(keep 190E) 3k_main_jianning` | **Weixian** | Dianchi, Wanwen, Qingling, Weixian, Tangao | Wu Dan (fill) `ironic_south_yizhou_c_resource_1` |
| Yongchang | `(keep 190E) 3k_dlc06_yongchang` | **Buwei** | Buwei, Yongshou | - |
| Yuexi | `3k_ironic_province_yuexi` | **Yuexi** | Yuexi | - |
| Zangke | `(keep 190E) 3k_main_zangke` | **Julan** | Julan, Yelang, Wulian | - |

### Jingzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Changsha | `(keep 190E) 3k_main_changsha` | **Linxiang** | Linxiang, Chibi, Lingxian, Chaling | Liandao (fill) `ironic_south_changsha_resource_1`<br>Yiyang (fill) `ironic_south_changsha_resource_2`<br>Ling (fill) `ironic_south_changsha_resource_3` |
| Guiyang | `3k_ironic_province_guiyang` | **Chenxian** | Chenxian, Nanping | Guiyang (fill) `ironic_south_guiyang_resource_1`<br>Han (fill) `ironic_south_guiyang_resource_2` |
| Jiangxia | `(keep 190E) 3k_main_jiangxia` | **Xiling** | Xiling, Xunyang | Zhu `ironic_central_jiangxia_resource_1`<br>Zhouling (fill) `ironic_central_jiangxia_resource_2`<br>E `ironic_central_jiangxia_resource_3` |
| Lingling | `(keep 190E) 3k_main_lingling` | **Quanling** | Quanling | Zhaoling (fill) `ironic_south_lingling_resource_1`<br>Duliang (fill) `ironic_south_lingling_resource_2`<br>Shi'an (fill) `ironic_south_lingling_resource_3` |
| Nan | `(keep 190E) 3k_main_jingzhou` | **Jiangling** | Jiangling, Huarong, linju | Fangling `ironic_central_nan_resource_1`<br>Ruo `ironic_central_nan_resource_2`<br>Dangyang (fill) `ironic_central_nan_resource_3` |
| Nanyang | `(keep 190E) 3k_main_nanyang` | **Wanxian** | Wanxian, Xinye, Xiangyang | Nanxiang `ironic_central_nanyang_resource_1` |
| Wuling | `(keep 190E) 3k_main_wuling` | **Qianling** | Linyuan, Qianling, Chongxian | Yuanling (fill) `ironic_south_wuling_resource_1`<br>Chenyang (fill) `ironic_south_wuling_resource_2` |

### Yangzhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Danyang | `(keep 190E) 3k_main_xindu` | **Shixin** | Jianye, Wanling, Shixin, Wuhu | Danyang (fill) `ironic_south_danyang_resource_1` |
| Jiujiang (Huainan) | `(keep 190E) 3k_main_yangzhou` | **Shouchun** | Hefei, Shouchun | - |
| Kuaiji | `(keep 190E) 3k_main_kuaiji` | **Shanyin** | Yongning, Shanyin, Linhai, Wushang, Xin'an | Mao (fill) `ironic_south_kuaiji_resource_1`<br>Dongbuhouguan (fill) `ironic_south_kuaiji_resource_2` |
| Lujiang | `3k_ironic_province_lujiang` | **Gushi** | Gushi | Anfeng `ironic_central_lujiang_resource_1` |
| Wu | `3k_ironic_province_wu` | **Wu** | Wu | Wucheng (fill) `ironic_south_wu_resource_1`<br>Dantu (fill) `ironic_south_wu_resource_2`<br>Fuchun (fill) `ironic_south_wu_resource_3` |
| Yuzhang | `(keep 190E) 3k_main_yuzhang` | **Nanchang** | Poyang, Haihun, Guangchang, Lean, Nanchang, Jianchang, Geyang | Ai (fill) `ironic_south_yuzhang_resource_1` |

### Jiaozhou

| commandery | province key | capital | existing towns | new towns |
|---|---|---|---|---|
| Cangwu | `(keep 190E) 3k_main_cangwu` | **Guangxin** | Guangxin, Fuchuan, Mengling | Linhe `ironic_south_cangwu_resource_1` |
| Hepu | `(keep 190E) 3k_main_hepu` | **Hepu** | Hepu, Xuwen | - |
| Jiaozhi | `(keep 190E) 3k_main_jiaozhi` | **Longbien** | Longbien, Xisui | - |
| Jiuzhen | `(keep 190E) 3k_dlc06_jiuzhen` | **Xupu** | Xupu | - |
| Nanhai | `(keep 190E) 3k_main_nanhai` | **Panyu** | Panyu, Longchuan | - |
| Rinan | `3k_ironic_province_rinan` | **Rinan** | Rinan | - |
| Yulin | `(keep 190E) 3k_main_yulin` | **Bushan** | Dingzhou, Bushan, Tanzhong | Anguang (fill) `ironic_south_yulin_resource_1`<br>Zengshi (fill) `ironic_south_yulin_resource_2` |

### Existing towns that keep their 190E province

These are towns with no reliable commandery match: no identified seat, or the matched seat is more than 250 km off (mostly Shang / Shuofang / Wuyuan / Yunzhong, absent from the AD 262 map, plus Korea and the tribes).

Gu Pass (`3k_dlc06_gu_pass`), Hangu Pass (`3k_dlc06_hangu_pass`), Hulao Pass (`3k_dlc06_hulao_pass`), Jiameng Pass (`3k_dlc06_jiameng_pass`), Kui Pass (`3k_dlc06_kui_pass`), Qi Pass (`3k_dlc06_qi_pass`), San Pass (`3k_dlc06_san_pass`), Tong Pass (`3k_dlc06_tong_pass`), Wu Pass (`3k_dlc06_wu_pass`), Farmland (`3k_dlc06_xiapi_resource_1`), Longdong (`3k_dlc06_yunnan_capital`), Yong'an (`3k_main_badong_capital`), Quren (`3k_main_badong_resource_1`), Hanchang (`3k_main_baxi_resource_1`), Wenma (`3k_main_dongou_resource_1`), Fuling (`3k_main_fuling_capital`), Jianwei (`3k_main_fuling_resource_1`), Siping (`3k_main_gaoliang_capital`), Anning (`3k_main_gaoliang_resource_1`), Jian'an (`3k_main_jianan_capital`), Jiangle (`3k_main_jianan_resource_1`), Jianping (`3k_main_jianan_resource_2`), Zhuti (`3k_main_jiangyang_resource_2`), Pingyi (`3k_main_jiangyang_resource_3`), Xiuyun (`3k_main_jianning_resource_2`), Linchen (`3k_main_jiaozhi_resource_1`), Shuxian (`3k_main_lujiang_resource_2`), Yudu (`3k_main_luling_capital`), Yangdu (`3k_main_luling_resource_1`), Jieyang (`3k_main_nanhai_resource_2`), Shangyong (`3k_main_shangyong_capital`), Shanglian (`3k_main_shangyong_resource_2`), Dong'an (`3k_main_tongan_capital`), Shashu (`3k_main_tongan_resource_1`), Chancheng (`3k_main_wuling_resource_2`), Juchao (`3k_main_yangzhou_resource_3`), Guangyu (`3k_main_yulin_resource_2`), Dongye (`ironic_region_dongye_capital`), Loufang (`ironic_region_dongye_resource_1`), Wirye-seong (`ironic_region_hanseong_capital`), Uhyumotak-guk (`ironic_region_hanseong_resource_2`), Daifang (`ironic_region_jinbeongun_capital`), Liekou  (`ironic_region_jinbeongun_resource_1`), Changcen  (`ironic_region_jinbeongun_resource_2`), Pyongyang (`ironic_region_lelang_capital`), Xi'anping (`ironic_region_lelang_resource_1`), Haslla (`ironic_region_ye_resource_1`)

### Optional (outside Kongming coverage)



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