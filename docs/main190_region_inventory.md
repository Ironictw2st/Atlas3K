# 190E region inventory (round 6 research)

Every land region of 190E (240, including the 9 gate passes), as it is **before** any new placement.
- **town lat/lon**: the region's town (slot 0) converted through `rubber.py` (the georef plus a correction onto 190E's own towns).
- **seat**: the Han county seat the region represents. CHGIS V5 county points valid 150–230 CE where the name matches within 250 km; otherwise `gazetteer_manual.json` (standard identifications; `approx` = area only). Blank = no Han county of that name (190E inventions, Korean states, generic names).
- **off**: km between the town and the seat. Up to ~100 km is the normal simplification of the game map; more is flagged ⚠.
- **imp**: share of impassable hexes in the region. **straight**: share of border hexes on straight runs of 8+ hexes (the natural-border rule).

Totals: 240 regions; seat identified 181; ⚠ off > 100 km: 53; straight > 0.3: 2.

## Anding

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_anding_capital` | Linjing | capital | 35.96,107.7 | Linjing 臨涇, Anding seat, Zhenyuan | manual:approx | 55 | 1438 | 0.19 | 0.0 |
| `3k_main_anding_resource_1` | Gaonu | resource | 36.64,109.3 | Gaonu 高奴, Yan'an | manual:sure | 17 | 2788 | 0.19 | 0.08 |
| `3k_main_anding_resource_2` | Canluan | resource | 36.72,107.86 | Canluan 參䜌, Anding | manual:approx | 160 ⚠ | 1538 | 0.04 | 0.04 |
| `3k_main_anding_resource_3` | Sanshui | resource | 37.52,106.62 | Sanshui 三水, Anding (Tongxin) | manual:approx | 57 | 1685 | 0.04 | 0.0 |

## Anping

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_anping_capital` | Xindu | capital | 37.54,115.25 | Xindu 信都, Anping seat, Jizhou city | manual:sure | 26 | 744 | 0.07 | 0.0 |
| `3k_main_anping_resource_1` | Julu | resource | 37.2,114.09 | Julu 鉅鹿 county, Pingxiang | manual:sure | 83 | 959 | 0.06 | 0.0 |

## Ba

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_bajun_capital` | Jiangzhou | capital | 29.35,106.7 | Jiangzhou Xian 江州县 | CHGIS | 28 | 1301 | 0.1 | 0.0 |
| `3k_main_bajun_resource_1` | Danqu | resource | 31.57,107.77 | Danqu 宕渠, Qu county | manual:sure | 111 ⚠ | 1260 | 0.15 | 0.07 |
| `3k_main_shangyong_resource_2` | Shanglian | resource | 31.34,108.9 |  |  |  | 1641 | 0.76 | 0.04 |

## Badong

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_badong_capital` | Yong'an | capital | 30.92,110.14 | Yong'an Xian 永安县 | CHGIS | 56 | 523 | 0.39 | 0.0 |
| `3k_main_badong_resource_1` | Quren | resource | 30.22,108.9 | Quren Xian 朐忍县 | CHGIS | 80 | 1357 | 0.77 | 0.06 |
| `3k_main_badong_resource_2` | Linyuan | resource | 29.29,111.43 | Linyuan Xian 临沅县 | CHGIS | 38 | 1941 | 0.59 | 0.0 |

## Baxi

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_baxi_capital` | Langzhong | capital | 31.59,106.4 | Langzhong Xian 阆中县 | CHGIS | 41 | 1036 | 0.13 | 0.0 |
| `3k_main_baxi_resource_2` | Zitong | resource | 31.85,104.99 | Zitong Xian 梓潼县 | CHGIS | 28 | 2146 | 0.05 | 0.0 |

## Beihai

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_beihai_capital` | Juxian | capital | 36.73,118.37 | Ju 莒, Ju county | manual:sure | 134 ⚠ | 313 | 0.0 | 0.0 |
| `3k_main_beihai_resource_1` | Jimo | resource | 36.58,119.26 | Jimo Houguo 即墨侯国 | CHGIS | 91 | 815 | 0.18 | 0.05 |

## Bohai

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_bohai_capital` | Nanpi | capital | 38.25,116.07 | Nanpi Xian 南皮县 | CHGIS | 60 | 585 | 0.09 | 0.0 |
| `3k_main_bohai_resource_1` | Zhangwu | resource | 38.53,116.92 | Zhangwu 章武, Huanghua/Dacheng | manual:approx | 21 | 599 | 0.0 | 0.0 |

## Byeonhan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_kimhae_capital` | Guya-guk | capital | 35.36,126.84 |  |  |  | 373 | 0.0 | 0.23 |
| `ironic_region_kimhae_resource_1` | Geochilsan-guk | resource | 35.17,127.41 |  |  |  | 176 | 0.01 | 0.22 |

## Cangwu

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_cangwu_capital` | Guangxin | capital | 23.71,111.07 | Guangxin Xian 广信县 | CHGIS | 35 | 1654 | 0.52 | 0.04 |
| `3k_main_cangwu_resource_1` | Fuchuan | resource | 25.2,111.17 | Fuchuan Xian 富川县 | CHGIS | 76 | 1380 | 0.65 | 0.03 |
| `3k_main_cangwu_resource_2` | Mengling | resource | 24.2,110.09 | Mengling Xian 猛陵县 | CHGIS | 127 ⚠ | 1217 | 0.36 | 0.04 |
| `3k_main_cangwu_resource_3` | Dingzhou | resource | 25.54,109.25 | Dingzhou Xian 定周县 | CHGIS | 132 ⚠ | 1768 | 0.63 | 0.03 |

## Changsha

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_changsha_capital` | Linxiang | capital | 28.14,112.83 | Linxiang Xian 临湘县 | CHGIS | 16 | 1349 | 0.43 | 0.0 |
| `3k_main_changsha_resource_1` | Chibi | resource | 29.3,113.36 | Chibi 赤壁 battlefield | manual:approx | 69 | 449 | 0.02 | 0.0 |
| `3k_main_changsha_resource_2` | Lingxian | resource | 27.02,112.24 | Ling 酃, Hengyang | manual:approx | 38 | 2040 | 0.39 | 0.06 |
| `3k_main_changsha_resource_3` | Chaling | resource | 26.85,113.18 | Chaling Xian 茶陵县 | CHGIS | 64 | 1680 | 0.45 | 0.0 |

## Chen

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_chenjun_capital` | Suiyang | capital | 33.69,115.22 | Suiyang Xian 睢阳县 | CHGIS | 93 | 993 | 0.14 | 0.0 |
| `3k_main_chenjun_resource_2` | Ruyang | resource | 32.84,114.0 | Ruyang Xian 汝阳县 | CHGIS | 94 | 1813 | 0.13 | 0.0 |

## Chimmi Darye

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_baek_capital` | Shinmi-guk | capital | 34.53,124.96 |  |  |  | 412 | 0.01 | 0.0 |
| `ironic_region_baek_resource_1` | Tamna | resource | 33.14,125.41 |  |  |  | 199 | 0.08 | 0.0 |
| `ironic_region_baek_resource_2` | Nakno-guk | resource | 34.77,125.82 |  |  |  | 266 | 0.0 | 0.17 |
| `ironic_region_baek_resource_3` | Anya-guk | resource | 35.12,126.44 |  |  |  | 437 | 0.14 | 0.11 |

## Dai

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_daijun_capital` | Gaoliu | capital | 39.56,114.79 | Gaoliu Xian 高柳县 | CHGIS | 125 ⚠ | 465 | 0.04 | 0.0 |
| `3k_main_daijun_resource_1` | Zhuo Lu | resource | 39.83,115.68 | Zhuolu 涿鹿 | manual:sure | 74 | 1063 | 0.2 | 0.1 |

## Daifang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_jinbeongun_capital` | Daifang | capital | 37.97,123.89 |  |  |  | 856 | 0.0 | 0.12 |
| `ironic_region_jinbeongun_resource_1` | Liekou  | resource | 38.28,125.45 |  |  |  | 312 | 0.01 | 0.12 |
| `ironic_region_jinbeongun_resource_2` | Changcen  | resource | 37.92,124.91 |  |  |  | 147 | 0.0 | 0.0 |

## Danyang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_jianye_capital` | Jianye | capital | 31.79,118.86 | Moling/Jianye, Nanjing | manual:sure | 30 | 1054 | 0.12 | 0.0 |
| `3k_main_jianye_resource_1` | Wu | resource | 31.18,120.83 | Wu Xian 吴县 | CHGIS | 25 | 824 | 0.03 | 0.0 |
| `3k_main_jianye_resource_2` | Wanling | resource | 30.89,119.25 | Wanling Xian 宛陵县 | CHGIS | 49 | 961 | 0.1 | 0.0 |

## Dong

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_dongjun_capital` | Puyang | capital | 36.03,115.96 | Puyang 濮陽, Dong commandery seat | manual:sure | 100 | 1189 | 0.38 | 0.0 |
| `3k_main_dongjun_resource_1` | Dongping | resource | 35.73,117.39 | Dongping (Wuyan 無鹽) | manual:approx | 86 | 892 | 0.57 | 0.0 |

## Donghai

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_donghai_capital` | Tanxian | capital | 34.37,118.22 | Tan 郯, Donghai seat, Tancheng | manual:sure | 28 | 663 | 0.05 | 0.08 |
| `3k_main_donghai_resource_1` | Haixi | resource | 33.89,120.19 | Haixi Xian 海西县 | CHGIS | 75 | 1102 | 0.1 | 0.0 |

## Donglai

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_donglai_capital` | Huangxian | capital | 37.56,119.84 | Huang 黃, Donglai seat, Longkou | manual:sure | 50 | 358 | 0.08 | 0.0 |
| `3k_main_donglai_resource_1` | Changyang | resource | 37.03,121.04 | Changyang Xian 昌阳县 | CHGIS | 86 | 1175 | 0.16 | 0.09 |

## Dongokjeo

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_dongokjeo_capital` | Gaema | capital | 40.16,126.15 |  |  |  | 2458 | 0.62 | 0.07 |
| `ironic_region_dongokjeo_resource_1` | Guda | resource | 40.76,127.36 |  |  |  | 2740 | 0.77 | 0.07 |
| `ironic_region_dongokjeo_resource_2` | Gungnae-seong | resource | 40.95,124.69 |  |  |  | 1780 | 0.7 | 0.0 |

## Dongye

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_dongye_capital` | Dongye | capital | 39.26,126.3 |  |  |  | 1173 | 0.06 | 0.1 |
| `ironic_region_dongye_resource_1` | Loufang | resource | 39.15,125.24 |  |  |  | 366 | 0.0 | 0.0 |

## Dunhuang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_hanyang_capital` | Dunhuang | capital | 39.34,100.34 | Dunhuang | manual:sure | 494 ⚠ | 3058 | 0.06 | 0.32 |
| `ironic_region_hanyang_resource_1` | Jiuquan | resource | 40.56,101.68 | Lufu 祿福, Jiuquan seat | manual:sure | 286 ⚠ | 1406 | 0.06 | 0.28 |

## Fuling

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_fuling_capital` | Fuling | capital | 28.99,108.36 |  |  |  | 1624 | 0.26 | 0.0 |
| `3k_main_fuling_resource_1` | Jianwei | resource | 27.89,107.3 |  |  |  | 1516 | 0.44 | 0.0 |

## Gaoliang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_gaoliang_capital` | Siping | capital | 22.64,112.11 |  |  |  | 1338 | 0.27 | 0.04 |
| `3k_main_gaoliang_resource_1` | Anning | resource | 22.22,111.06 | Anning Xian 安宁县 | CHGIS | 94 | 866 | 0.6 | 0.0 |

## Gu Pass

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_gu_pass` | Gu Pass | pass | 36.39,111.95 |  |  |  | 89 | 0.16 | 0.0 |

## Guangling

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_guangling_capital` | Huaiyin | capital | 33.13,119.07 | Huaiyin Xian 淮阴县 | CHGIS | 47 | 1229 | 0.05 | 0.07 |
| `3k_main_guangling_resource_1` | Gaoyou | resource | 32.61,119.94 | Gaoyou Xian 高邮县 | CHGIS | 51 | 913 | 0.11 | 0.0 |
| `3k_main_guangling_resource_2` | Jiangdu | resource | 31.92,120.22 | Jiangdu Xian 江都县 | CHGIS | 82 | 598 | 0.0 | 0.0 |

## Guangyang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_youzhou_capital` | Ji | capital | 39.75,116.38 | Ji 薊, Youzhou / Guangyang seat, Beijing | manual:sure | 16 | 575 | 0.13 | 0.07 |
| `3k_main_youzhou_resource_1` | Junmi | resource | 40.22,117.63 | Jundu 軍都, Changping | manual:approx | 121 ⚠ | 347 | 0.03 | 0.0 |

## Hangu Pass

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_hangu_pass` | Hangu Pass | pass | 34.47,111.34 |  |  |  | 107 | 0.0 | 0.0 |

## Hanseong

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_hanseong_capital` | Wirye-seong | capital | 37.61,125.68 |  |  |  | 645 | 0.0 | 0.17 |
| `ironic_region_hanseong_resource_1` | Michuhol | resource | 37.05,125.42 |  |  |  | 367 | 0.0 | 0.12 |
| `ironic_region_hanseong_resource_2` | Uhyumotak-guk | resource | 38.04,126.38 |  |  |  | 337 | 0.0 | 0.26 |

## Hanzhong

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_hanzhong_capital` | Nanzheng | capital | 33.2,107.12 | Nanzheng Xian 南郑县 | CHGIS | 16 | 718 | 0.04 | 0.0 |
| `3k_main_baxi_resource_1` | Hanchang | resource | 32.45,107.42 | Hanchang Xian 汉昌县 | CHGIS | 91 | 1058 | 0.53 | 0.0 |

## Hedong

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_hedong_capital` | Anyi | capital | 35.29,110.57 | Anyi Xian 安邑县 | CHGIS | 55 | 291 | 0.19 | 0.0 |
| `3k_dlc06_hedong_resource_2` | Pingyang | resource | 36.01,111.0 | Pingyang Xian 平阳县 | CHGIS | 38 | 908 | 0.52 | 0.0 |
| `3k_main_hedong_resource_1` | Puzhou | resource | 35.06,109.96 | Puban 蒲坂, Yongji | manual:sure | 43 | 584 | 0.19 | 0.0 |

## Henei

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_henei_capital` | Huaixian | capital | 35.49,114.47 | Huai 懷, Henei seat, Wuzhi | manual:sure | 126 ⚠ | 532 | 0.04 | 0.0 |
| `3k_dlc06_shangdang_resource_2` | Zhixian | resource | 35.5,113.06 | Zhi 軹, Jiyuan | manual:sure | 66 | 658 | 0.01 | 0.06 |
| `3k_main_henei_resource_1` | Zhaoge | resource | 36.32,115.47 | Zhaoge 朝歌, Qi county | manual:sure | 139 ⚠ | 443 | 0.05 | 0.0 |

## Hepu

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_hepu_capital` | Hepu | capital | 21.93,108.52 | Hepu Xian 合浦县 | CHGIS | 98 | 914 | 0.17 | 0.1 |
| `3k_main_hepu_resource_1` | Xuwen | resource | 21.61,109.92 | Xuwen Xian 徐闻县 | CHGIS | 152 ⚠ | 1145 | 0.01 | 0.04 |
| `3k_main_hepu_resource_2` | Zhuya | resource | 20.08,109.88 | Zhuya Xian 朱崖县 | CHGIS | 67 | 1947 | 0.18 | 0.0 |

## Huainan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_yangzhou_capital` | Shouchun | capital | 32.01,117.06 | Shouchun Xian 寿春县 | CHGIS | 68 | 821 | 0.04 | 0.0 |
| `3k_main_yangzhou_resource_3` | Juchao | resource | 31.32,117.52 | Juchao Houguo 居巢侯国 | CHGIS | 71 | 901 | 0.1 | 0.13 |

## Hulao Pass

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_hulao_pass` | Hulao Pass | pass | 34.74,113.33 |  |  |  | 77 | 0.06 | 0.0 |

## Hyunto

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_hyunto_capital` | Hyunto | capital | 42.06,122.02 |  |  |  | 870 | 0.55 | 0.0 |
| `ironic_region_hyunto_resource_1` | Liaodui | resource | 41.56,123.53 |  |  |  | 1812 | 0.25 | 0.0 |
| `ironic_region_hyunto_resource_2` | Changli | resource | 42.23,121.12 | Changli 昌黎 (Liaodong Shuguo), Yixian | manual:approx | 78 | 2541 | 0.8 | 0.1 |

## Jiameng Pass

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_jiameng_pass` | Jiameng Pass | pass | 32.92,106.15 |  |  |  | 60 | 0.25 | 0.0 |

## Jiangxia

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_jiangxia_capital` | Xiling | capital | 30.23,113.63 | Xiling Xian 西陵县 | CHGIS | 129 ⚠ | 1088 | 0.51 | 0.04 |
| `3k_main_jiangxia_resource_1` | Xiyang | resource | 30.91,114.24 | Xiyang Xian 西阳县 | CHGIS | 139 ⚠ | 838 | 0.21 | 0.06 |

## Jiangyang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_jiangyang_capital` | Jiangyang | capital | 28.7,105.47 | Jiangyang Xian 江阳县 | CHGIS | 21 | 779 | 0.02 | 0.14 |
| `3k_main_jiangyang_resource_1` | Wuyang | resource | 29.44,103.87 | Wuyang Xian 武阳县 | CHGIS | 95 | 1714 | 0.51 | 0.05 |
| `3k_main_jiangyang_resource_2` | Zhuti | resource | 28.13,104.24 | Zhuti Xian 朱提县 | CHGIS | 101 ⚠ | 1398 | 0.51 | 0.0 |
| `3k_main_jiangyang_resource_3` | Pingyi | resource | 27.94,105.61 |  |  |  | 1326 | 0.53 | 0.0 |

## Jianning

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_jianning_capital` | Weixian | capital | 26.24,103.84 | Wei 味, Qujing | manual:approx | 83 | 468 | 0.06 | 0.0 |
| `3k_dlc06_jianning_resource_3` | Dianchi | resource | 25.37,103.04 | Dianchi Xian 滇池县 | CHGIS | 80 | 1377 | 0.37 | 0.0 |
| `3k_main_jianning_resource_1` | Tangao | resource | 26.45,104.62 | Tangao Xian 谈稿县 | CHGIS | 102 ⚠ | 1117 | 0.34 | 0.05 |
| `3k_main_jianning_resource_2` | Xiuyun | resource | 24.31,104.22 |  |  |  | 1009 | 0.46 | 0.0 |

## Jiaozhi

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_jiaozhi_capital` | Longbien | capital | 21.97,106.47 | Longbian 龍編, Jiaozhi seat, near Hanoi | manual:sure | 119 ⚠ | 1082 | 0.1 | 0.0 |
| `3k_dlc06_jiaozhi_resource_3` | Wanwen | resource | 24.2,105.84 | Wanwen Xian 宛温县 | CHGIS | 167 ⚠ | 2217 | 0.69 | 0.0 |
| `3k_main_jiaozhi_resource_1` | Linchen | resource | 22.59,107.33 | Linchen Xian 临尘县 | CHGIS | 19 | 1400 | 0.66 | 0.0 |
| `3k_main_jiaozhi_resource_2` | Xisui | resource | 23.19,105.44 | Xiyu 西于, Jiaozhi | manual:approx | 222 ⚠ | 2434 | 0.56 | 0.0 |

## Jincheng

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_jincheng_capital` | Jincheng | capital | 36.24,103.84 | Jincheng Xian 金城县 | CHGIS | 22 | 1208 | 0.2 | 0.0 |
| `3k_main_jincheng_resource_1` | Zhanyin | resource | 37.0,105.41 | Zhanyin 鸇陰, Jingyuan | manual:approx | 77 | 1296 | 0.16 | 0.0 |
| `3k_main_jincheng_resource_2` | Tianshui | resource | 35.52,105.79 | Ji 冀, Hanyang (Tianshui) seat, Gangu | manual:sure | 94 | 1053 | 0.2 | 0.0 |

## Jingzhao

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_changan_capital` | Chang'an | capital | 34.27,108.79 | Changan Xian 长安县 | CHGIS | 15 | 1206 | 0.21 | 0.09 |
| `3k_main_changan_resource_1` | Lantian | resource | 33.62,108.95 | Lantian Xian 蓝田县 | CHGIS | 71 | 981 | 0.95 | 0.03 |
| `3k_main_hanzhong_resource_1` | Meixian | resource | 34.06,107.9 | Mei 郿, Dong Zhuo's Meiwu | manual:sure | 28 | 1371 | 0.68 | 0.04 |

## Jinhan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_gyeongju_capital` | Seorabeol | capital | 35.91,127.83 |  |  |  | 572 | 0.0 | 0.0 |
| `ironic_region_gyeongju_resource_1` | Dabeol-guk | resource | 35.83,126.96 |  |  |  | 341 | 0.17 | 0.0 |

## Jiuzhen

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_jiuzhen_capital` | Xupu | capital | 20.72,105.88 | Xupu 胥浦, Jiuzhen seat, Thanh Hoa | manual:approx | 103 ⚠ | 1643 | 0.13 | 0.0 |
| `3k_dlc06_jiuzhen_resource_1` | Rinan | resource | 19.16,105.96 | Rinan commandery (Xijuan 西捲), central Vietnam | manual:approx | 289 ⚠ | 1895 | 0.39 | 0.09 |

## Kuaiji

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_kuaiji_capital` | Shanyin | capital | 29.86,120.71 | Shanyin Xian 山阴县 | CHGIS | 20 | 959 | 0.31 | 0.0 |
| `3k_main_kuaiji_resource_1` | Linhai | resource | 28.75,120.87 | Linhai 臨海 area, Taizhou | manual:approx | 25 | 1232 | 0.47 | 0.0 |
| `3k_main_kuaiji_resource_2` | Wushang | resource | 29.12,119.88 | Wushang Xian 乌伤县 | CHGIS | 27 | 666 | 0.3 | 0.0 |

## Kui Pass

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_kui_pass` | Kui Pass | pass | 31.25,110.16 |  |  |  | 114 | 0.47 | 0.0 |

## Langya

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_langye_capital` | Dongwu | capital | 35.91,119.52 | Dongwu Houguo 东武侯国 | CHGIS | 14 | 540 | 0.08 | 0.0 |
| `3k_main_langye_resource_1` | Kaiyang | resource | 35.28,118.34 | Kaiyang Xian 开阳县 | CHGIS | 15 | 1048 | 0.22 | 0.05 |
| `3k_main_langye_resource_2` | Buji | resource | 36.39,120.21 | Buqi 不其, Qingdao Chengyang | manual:approx | 23 | 309 | 0.01 | 0.0 |

## Lean

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_taishan_capital` | Dongpingling | capital | 36.59,117.36 | Dongpingling Xian 东平陵县 | CHGIS | 19 | 543 | 0.0 | 0.08 |
| `3k_main_taishan_resource_1` | Lean | resource | 37.26,118.41 | Lean Xian 乐安县 | CHGIS | 23 | 367 | 0.3 | 0.09 |

## Lelang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_lelang_capital` | Pyongyang | capital | 39.32,124.58 |  |  |  | 620 | 0.0 | 0.17 |
| `ironic_region_lelang_resource_1` | Xi'anping | resource | 39.73,123.66 |  |  |  | 1741 | 0.0 | 0.0 |

## Liaodong

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_liaodong_capital` | Xiangping | capital | 40.48,121.59 | Xiangping 襄平, Liaodong seat = Liaoyang | manual:sure | 159 ⚠ | 2219 | 0.05 | 0.0 |
| `3k_dlc06_liaodong_resource_1` | Xuantu | resource | 41.38,120.8 | Xuantu 玄菟 (Gaogouli county), east of Shenyang | manual:approx | 263 ⚠ | 1158 | 0.19 | 0.0 |

## Liaoxi

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_yu_capital` | Yangle | capital | 41.19,119.75 | Yangle 陽樂 (disputed) | manual:approx | 83 | 383 | 0.23 | 0.0 |
| `3k_main_yu_resource_1` | Liucheng | resource | 40.74,118.74 | Liucheng 柳城, Chaoyang | manual:sure | 171 ⚠ | 424 | 0.23 | 0.0 |

## Lingling

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_lingling_capital` | Quanling | capital | 26.08,111.4 | Quanling Xian 泉陵县 | CHGIS | 25 | 2724 | 0.54 | 0.0 |
| `3k_main_lingling_resource_1` | Chenxian | resource | 25.79,113.31 | Chen 郴, Guiyang seat, Chenzhou | manual:sure | 28 | 910 | 0.25 | 0.0 |
| `3k_main_lingling_resource_2` | Nanping | resource | 25.14,112.28 | Nanping Xian 南平县 | CHGIS | 28 | 654 | 0.33 | 0.09 |

## Linhai

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_dongou_capital` | Yongning | capital | 27.64,120.55 | Yongning Xian 永宁县 | CHGIS | 43 | 549 | 0.19 | 0.0 |
| `3k_main_dongou_resource_1` | Wenma | resource | 26.58,119.74 |  |  |  | 702 | 0.23 | 0.0 |

## Lujiang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_lujiang_capital` | Hefei | capital | 31.07,116.26 | Hefei Xian 合肥县 | CHGIS | 130 ⚠ | 1740 | 0.07 | 0.05 |
| `3k_main_lujiang_resource_1` | Xunyang | resource | 29.05,114.97 | Xunyang Xian 寻阳县 | CHGIS | 119 ⚠ | 1241 | 0.56 | 0.0 |
| `3k_main_lujiang_resource_2` | Shuxian | resource | 30.15,116.52 | Shu 舒, Lujiang | manual:approx | 113 ⚠ | 634 | 0.04 | 0.0 |

## Luling

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_luling_capital` | Yudu | capital | 25.93,114.68 | Yudu 雩都 | manual:sure | 73 | 2137 | 0.43 | 0.03 |
| `3k_main_luling_resource_1` | Yangdu | resource | 26.65,117.08 | Yangdu Xian 杨都县 | CHGIS | 121 ⚠ | 1042 | 0.76 | 0.0 |

## Luoyang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_luoyang_capital` | Luoyang | capital | 34.69,112.88 | Luoyang Xian 雒阳县 | CHGIS | 26 | 969 | 0.14 | 0.0 |
| `3k_main_luoyang_resource_1` | Hongnong | resource | 34.55,110.44 | Hongnong Xian 弘农县 | CHGIS | 46 | 1669 | 0.45 | 0.0 |

## Mahan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_baekje_capital` | Mokji-guk | capital | 36.31,125.6 |  |  |  | 718 | 0.0 | 0.0 |
| `ironic_region_baekje_resource_1` | Gori-guk | resource | 36.77,126.3 |  |  |  | 655 | 0.0 | 0.15 |
| `ironic_region_baekje_resource_2` | Geonma-guk | resource | 35.51,125.62 |  |  |  | 888 | 0.08 | 0.06 |

## Nan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_jingzhou_capital` | Jiangling | capital | 29.92,111.63 | Jiangling Xian 江陵县 | CHGIS | 72 | 1147 | 0.0 | 0.12 |
| `3k_main_jingzhou_resource_1` | Huarong | resource | 30.42,112.58 | Huarong Houguo 华容侯国 | CHGIS | 28 | 1824 | 0.06 | 0.04 |

## Nanhai

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_nanhai_capital` | Panyu | capital | 23.12,113.35 | Panyu 番禺, Nanhai seat, Guangzhou | manual:sure | 10 | 1550 | 0.08 | 0.04 |
| `3k_main_nanhai_resource_1` | Longchuan | resource | 24.32,114.21 | Longchuan Xian 龙川县 | CHGIS | 103 ⚠ | 2777 | 0.6 | 0.03 |
| `3k_main_nanhai_resource_2` | Jieyang | resource | 23.62,116.23 | Jieyang Xian 揭阳县 | CHGIS | 8 | 2358 | 0.49 | 0.0 |

## Nanyang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_nanyang_capital` | Wanxian | capital | 33.3,112.15 | Wan 宛, Nanyang seat, Nanyang city | manual:sure | 49 | 898 | 0.02 | 0.0 |
| `3k_main_chenjun_resource_3` | Liangxian | resource | 33.81,112.9 | Liang 梁 county, Ruzhou | manual:approx | 40 | 864 | 0.47 | 0.0 |
| `3k_main_nanyang_resource_1` | Xinye | resource | 32.47,112.52 | Xinye Xian 新野县 | CHGIS | 16 | 1075 | 0.19 | 0.05 |

## Northern Jian'an

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_jianan_capital` | Jian'an | capital | 27.36,118.6 | Jian'an 建安, Jian'ou | manual:sure | 46 | 1400 | 0.7 | 0.0 |
| `3k_main_jianan_resource_1` | Jiangle | resource | 27.5,117.85 | Jiangle 將樂 | manual:approx | 94 | 1326 | 0.89 | 0.0 |
| `3k_main_jianan_resource_2` | Jianping | resource | 28.48,119.03 | Jianping Xian 建平县 | CHGIS | 175 ⚠ | 1063 | 0.31 | 0.05 |

## Pei

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_chenjun_resource_1` | Peixian | resource | 33.24,116.08 | Pei 沛, Pei county | manual:sure | 184 ⚠ | 967 | 0.12 | 0.0 |
| `3k_main_yangzhou_resource_1` | Fuli | resource | 32.81,116.92 | Fuli Xian 符离县 | CHGIS | 101 ⚠ | 624 | 0.03 | 0.0 |

## Pengcheng

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_penchang_capital` | Pengcheng | capital | 33.72,116.46 | Pengcheng Xian 彭城县 | CHGIS | 91 | 522 | 0.06 | 0.0 |
| `3k_main_penchang_resource_1` | Luxian | resource | 34.63,116.53 | Lu Xian 鲁县 | CHGIS | 115 ⚠ | 1172 | 0.3 | 0.0 |

## Pingyuan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_pingyuan_capital` | Pingyuan | capital | 37.31,116.57 | Pingyuan Xian 平原县 | CHGIS | 35 | 736 | 0.11 | 0.06 |
| `3k_main_pingyuan_resource_1` | Leling | resource | 37.65,117.47 | Leling Xian 乐陵县 | CHGIS | 23 | 731 | 0.07 | 0.0 |

## Poyang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_poyang_capital` | Poyang | capital | 28.29,116.44 | Poyang Xian 鄱阳县 | CHGIS | 98 | 1582 | 0.07 | 0.0 |
| `3k_main_poyang_resource_1` | Haihun | resource | 28.47,114.99 | Haihun Houguo 海昏侯国 | CHGIS | 102 ⚠ | 1264 | 0.38 | 0.04 |
| `3k_main_poyang_resource_2` | Guangchang | resource | 29.28,116.78 | Guangchang Xian 广昌县 | CHGIS | 33 | 664 | 0.0 | 0.09 |
| `3k_main_poyang_resource_3` | Lean | resource | 28.89,117.73 | Le'an Xian 乐安县 | CHGIS | 33 | 559 | 0.24 | 0.08 |

## Qi Pass

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_qi_pass` | Qi Pass | pass | 34.95,111.7 |  |  |  | 83 | 0.22 | 0.0 |

## Runan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_runan_capital` | Ruyin | capital | 31.64,114.55 | Ruyin Xian 汝阴县 | CHGIS | 184 ⚠ | 747 | 0.1 | 0.0 |
| `3k_main_runan_resource_1` | Pingyu | resource | 31.52,113.12 | Pingyu 平輿, Runan seat | manual:sure | 213 ⚠ | 1628 | 0.18 | 0.0 |
| `3k_main_yangzhou_resource_2` | Gushi | resource | 32.19,115.59 | Gushi 固始 area | manual:approx | 6 | 847 | 0.09 | 0.0 |

## San Pass

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_san_pass` | San Pass | pass | 34.47,107.29 |  |  |  | 135 | 0.08 | 0.37 |

## Shangdang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_shangdang_capital` | Zhangzi | capital | 35.61,111.97 | Zhangzi 長子, Shangdang seat | manual:sure | 108 ⚠ | 900 | 0.65 | 0.04 |
| `3k_main_shangdang_resource_1` | Shexian | resource | 36.42,113.04 | She 涉 | manual:approx | 59 | 680 | 0.16 | 0.06 |

## Shangyong

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_shangyong_capital` | Shangyong | capital | 32.39,109.8 | Shangyong Xian 上庸县 | CHGIS | 46 | 446 | 0.3 | 0.0 |
| `3k_main_shangyong_resource_1` | Xicheng | resource | 32.66,108.77 | Xicheng Xian 西城县 | CHGIS | 23 | 1174 | 0.15 | 0.0 |

## Shu

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_chengdu_capital` | Chengdu | capital | 30.51,104.06 | Chengdu Xian 成都县 | CHGIS | 15 | 736 | 0.12 | 0.0 |
| `3k_main_chengdu_resource_1` | Hanjia | resource | 30.12,103.08 | Hanjia Xian 汉嘉县 | CHGIS | 16 | 1451 | 0.06 | 0.0 |
| `3k_main_chengdu_resource_2` | Luocheng | resource | 30.65,105.69 | Luo 雒, Guanghan | manual:sure | 129 ⚠ | 1968 | 0.07 | 0.11 |
| `3k_main_chengdu_resource_3` | Zizhong | resource | 29.97,104.85 | Zizhong Xian 资中县 | CHGIS | 26 | 1840 | 0.05 | 0.16 |

## Shuofang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_shoufang_capital` | Heyin | capital | 40.04,109.33 |  |  |  | 1481 | 0.03 | 0.11 |
| `3k_main_shoufang_resource_1` | Pingding | resource | 38.51,109.44 |  |  |  | 1769 | 0.04 | 0.04 |
| `3k_main_shoufang_resource_2` | Dacheng | resource | 39.27,108.03 | Shuofang area | manual:approx | 150 ⚠ | 2460 | 0.03 | 0.1 |
| `3k_main_shoufang_resource_3` | Sheyan | resource | 38.14,107.72 |  |  |  | 889 | 0.0 | 0.07 |

## Southern Jian'an

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_tongan_capital` | Dong'an | capital | 24.81,117.88 |  |  |  | 1651 | 0.53 | 0.0 |
| `3k_main_tongan_resource_1` | Shashu | resource | 26.21,118.12 |  |  |  | 1736 | 0.25 | 0.0 |

## Taiyuan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_taiyuan_capital` | Jinyang | capital | 37.5,112.04 | Jinyang 晉陽, Taiyuan seat | manual:sure | 45 | 515 | 0.03 | 0.0 |
| `3k_main_taiyuan_resource_1` | Jingxing | resource | 37.5,112.89 | Jingxing 井陘 pass | manual:approx | 126 ⚠ | 1481 | 0.66 | 0.07 |
| `3k_main_taiyuan_resource_2` | Jiexiu | resource | 36.6,111.66 | Jiexiu Xian 界休县 | CHGIS | 53 | 362 | 0.38 | 0.0 |

## Tong Pass

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_tong_pass` | Tong Pass | pass | 34.37,109.97 |  |  |  | 183 | 0.7 | 0.0 |

## Wei

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_weijun_capital` | Ye | capital | 36.76,114.86 | Ye Xian 邺县 | CHGIS | 68 | 861 | 0.09 | 0.07 |
| `3k_main_weijun_resource_1` | Gongcheng | resource | 35.95,114.04 | Gong 共, Huixian | manual:approx | 59 | 1024 | 0.06 | 0.08 |

## Wu Pass

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_wu_pass` | Wu Pass | pass | 33.97,109.69 |  |  |  | 114 | 0.28 | 0.0 |

## Wudu

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_wudu_capital` | Xiabian | capital | 34.05,105.99 | Xiabian 下辨, Wudu seat, Cheng county | manual:approx | 43 | 826 | 0.73 | 0.06 |
| `3k_main_wudu_resource_1` | Shanggui | resource | 34.91,106.63 | Shanggui 上邽, Tianshui | manual:sure | 91 | 984 | 0.51 | 0.04 |
| `3k_main_wudu_resource_2` | Yinping | resource | 33.5,105.29 | Yinping 陰平, Wen county | manual:approx | 71 | 1111 | 0.61 | 0.0 |

## Wuling

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_wuling_capital` | Qianling | capital | 28.04,109.32 | Qianling Xian 迁陵县 | CHGIS | 81 | 1502 | 0.55 | 0.05 |
| `3k_main_wuling_resource_1` | Chongxian | resource | 29.05,109.72 | Chong Xian 充县 | CHGIS | 58 | 2707 | 0.48 | 0.0 |
| `3k_main_wuling_resource_2` | Chancheng | resource | 26.6,109.39 |  |  |  | 1851 | 0.37 | 0.0 |

## Wuwei

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_wuwei_capital` | Guzang | capital | 38.16,102.98 | Guzang 姑臧, Wuwei seat | manual:sure | 39 | 1531 | 0.04 | 0.03 |
| `3k_main_wuwei_resource_1` | Xiutu | resource | 38.35,104.55 | Xiutu 休屠 | manual:approx | 154 ⚠ | 1507 | 0.0 | 0.05 |
| `3k_main_wuwei_resource_2` | Lingzhou | resource | 38.87,106.12 |  |  |  | 836 | 0.17 | 0.0 |
| `ironic_region_wuwei_resource_3` | Rile | resource | 39.7,104.46 | Rile 日勒, Shandan | manual:approx | 315 ⚠ | 2093 | 0.01 | 0.23 |

## Wuyuan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_wuyuan_capital` | Wuyuan | capital | 40.54,108.48 |  |  |  | 1142 | 0.27 | 0.0 |
| `ironic_region_wuyuan_resource_1` | Yuan | resource | 39.63,106.08 |  |  |  | 805 | 0.46 | 0.06 |

## Xiangyang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_xiangyang_capital` | Xiangyang | capital | 32.15,111.75 | Xiangyang Xian 襄阳县 | CHGIS | 41 | 1021 | 0.22 | 0.05 |
| `3k_main_xiangyang_resource_1` | linju | resource | 31.39,110.9 | Linju Houguo 临沮侯国 | CHGIS | 91 | 1907 | 0.61 | 0.05 |

## Xiapi

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_xiapi_capital` | Xiapi | capital | 33.87,117.47 | Xiapi Xian 下邳县 | CHGIS | 47 | 1131 | 0.18 | 0.0 |
| `3k_dlc06_xiapi_resource_1` | Farmland | resource | 34.57,117.55 |  |  |  | 666 | 0.06 | 0.0 |

## Xihe

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_xihe_capital` | Lishi | capital | 37.7,110.68 | Lishi Xian 离石县 | CHGIS | 45 | 479 | 0.11 | 0.0 |
| `3k_main_xihe_resource_1` | Mengmen | resource | 36.81,110.04 | Xihe area (Lishi / Linxian) | manual:approx | 131 ⚠ | 1072 | 0.66 | 0.0 |

## Xindu

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_xindu_capital` | Shixin | capital | 29.83,118.77 | Shixin Xian 始新县 | CHGIS | 31 | 1109 | 0.31 | 0.0 |
| `3k_main_xindu_resource_1` | Xin'an | resource | 29.25,118.47 | Xin'an Xian 新安县 | CHGIS | 53 | 688 | 0.56 | 0.0 |
| `3k_main_xindu_resource_2` | Wuhu | resource | 30.3,117.35 | Wuhu Xian 芜湖县 | CHGIS | 150 ⚠ | 1423 | 0.43 | 0.0 |

## Xiping

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_xiping_capital` | Xidu | capital | 36.05,101.4 | Xidu 西都, Xining | manual:sure | 71 | 3592 | 0.39 | 0.0 |
| `ironic_region_xiping_resource_1` | Nan'an | resource | 37.36,100.84 |  |  |  | 4647 | 0.54 | 0.11 |
| `ironic_region_xiping_resource_2` | Huandao | resource | 35.76,100.69 |  |  |  | 2121 | 0.1 | 0.0 |

## Yanmen

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_yanmen_capital` | Yinguan | capital | 38.92,112.03 | Yinguan Xian 阴馆县 | CHGIS | 70 | 651 | 0.64 | 0.0 |
| `3k_main_yanmen_resource_1` | Fanzhi | resource | 39.16,113.77 | Fanzhi Xian 繁畤县 | CHGIS | 63 | 700 | 0.25 | 0.0 |

## Ye

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_ye_capital` | Siljik-guk | capital | 36.96,127.76 |  |  |  | 1362 | 0.15 | 0.14 |
| `ironic_region_ye_resource_1` | Haslla | resource | 38.09,127.41 |  |  |  | 548 | 0.24 | 0.09 |

## Yingchuan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_yingchuan_capital` | Xuchang | capital | 34.2,113.92 | Xu 許, Xuchang | manual:sure | 19 | 904 | 0.21 | 0.06 |
| `3k_main_yingchuan_resource_1` | Chenliu | resource | 35.03,114.69 | Chenliu Xian 陈留县 | CHGIS | 43 | 846 | 0.23 | 0.07 |

## Yizhou

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_yizhou_island_capital` | Danshui | capital | 24.78,121.09 |  |  |  | 675 | 0.19 | 0.0 |
| `3k_main_yizhou_island_resource_1` | Chiqian | resource | 22.67,119.95 |  |  |  | 1053 | 0.32 | 0.0 |

## Yongchang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_yongchang_capital` | Buwei | capital | 25.16,100.32 | Buwei Xian 不韦县 | CHGIS | 107 ⚠ | 1263 | 0.37 | 0.08 |
| `3k_dlc06_yongchang_resource_1` | Yongshou | resource | 24.43,101.92 | Yongchang area (Baoshan) | manual:approx | 310 ⚠ | 2029 | 0.45 | 0.0 |

## Youbeiping

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_youbeiping_capital` | Tuyin | capital | 39.53,117.52 | Tuyin 土垠, Fengrun | manual:approx | 61 | 711 | 0.0 | 0.0 |
| `3k_main_youbeiping_resource_1` | Linyu | resource | 39.89,118.94 | Linyu 臨渝, Shanhaiguan | manual:approx | 71 | 697 | 0.22 | 0.0 |

## Yulin

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_yulin_capital` | Bushan | capital | 22.87,109.63 | Bushan Xian 布山县 | CHGIS | 48 | 955 | 0.16 | 0.0 |
| `3k_main_yulin_resource_1` | Tanzhong | resource | 23.57,109.17 | Tanzhong Xian 潭中县 | CHGIS | 83 | 1164 | 0.13 | 0.05 |
| `3k_main_yulin_resource_2` | Guangyu | resource | 24.17,108.37 | Guangyu Xian 广郁县 | CHGIS | 161 ⚠ | 1741 | 0.46 | 0.0 |

## Yunnan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_dlc06_yunnan_capital` | Longdong | capital | 26.0,101.26 |  |  |  | 708 | 0.34 | 0.0 |
| `3k_dlc06_yunnan_resource_1` | Qingling | resource | 26.2,102.24 | Qingling Xian 青蛉县 | CHGIS | 106 ⚠ | 1533 | 0.36 | 0.09 |
| `3k_dlc06_yunnan_resource_2` | Yuexi | resource | 27.62,102.46 | Yuexi 越巂 (Qiongdu), Xichang | manual:sure | 36 | 2169 | 0.37 | 0.04 |

## Yuzhang

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_yuzhang_capital` | Nanchang | capital | 27.49,115.65 | Nanchang Xian 南昌县 | CHGIS | 134 ⚠ | 774 | 0.37 | 0.0 |
| `3k_main_yuzhang_resource_1` | Jianchang | resource | 27.28,114.71 | Jianchang Xian 建昌县 | CHGIS | 161 ⚠ | 1306 | 0.4 | 0.0 |
| `3k_main_yuzhang_resource_2` | Geyang | resource | 27.56,116.82 | Geyang Xian 葛阳县 | CHGIS | 111 ⚠ | 574 | 0.05 | 0.0 |

## Zangke

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_zangke_capital` | Julan | capital | 26.34,107.62 | Julan 且蘭, Zangke | manual:approx | 31 | 1464 | 0.47 | 0.04 |
| `3k_main_zangke_resource_1` | Yelang | resource | 26.52,105.99 | Yelang Xian 夜郎县 | CHGIS | 94 | 1779 | 0.5 | 0.07 |
| `3k_main_zangke_resource_2` | Wulian | resource | 25.44,107.5 | Wulian Xian 毋敛县 | CHGIS | 44 | 1512 | 0.55 | 0.0 |

## Zhangye

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `ironic_region_xi_capital` | Lude | capital | 38.69,102.48 | Lude 觻得, Zhangye seat | manual:sure | 178 ⚠ | 3029 | 0.0 | 0.28 |
| `ironic_region_xi_resource_1` | Xihai | resource | 40.73,104.68 | Juyan / Xihai area | manual:approx | 326 ⚠ | 2746 | 0.1 | 0.19 |

## Zhongshan

| key | name | kind | town lat,lon | seat | src | off km | hexes | imp | straight |
|---|---|---|---|---|---|---|---|---|---|
| `3k_main_zhongshan_capital` | Lunu | capital | 38.41,114.77 | Lunu 盧奴, Zhongshan seat, Dingzhou | manual:sure | 22 | 675 | 0.08 | 0.14 |
| `3k_main_zhongshan_resource_1` | Changshan | resource | 38.32,113.73 | Changshan Guo 常山国 | CHGIS | 82 | 903 | 0.08 | 0.0 |
