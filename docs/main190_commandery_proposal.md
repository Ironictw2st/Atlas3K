# main190 round 7 — commandery-accurate carve proposal (Sili, Yan, Yu, Yang-Wei, Qing, Xu, Jing-Wei, Ji)

Research + proposal only — nothing was placed. The machine-readable version is `research/main190/research_r6/candidates_r7.json`. Previews are in `research/main190/previews/r7_proposal_<zhou>.png` (current map with the proposal overlaid) and `r7_proposal_<zhou>_after.png` (estimated result). Scratch scripts are in `research/main190/research_r6/r7/`.

**Map state used.** This uses a snapshot of `hex/map.hex` taken 2026-09-30 12:36 (the round-6 carve). Round 6 is still running, and between runs it switched between two variants: Jiyin as one region or as Dingtao+Chengwu, and Qufu, Changyi and Juye in different places. So the plan gives **target sites (lat/lon)**, not offsets. Where a key differs between the variants, `plan.py` accepts either (`a|b`). All hex coordinates in this document refer to that snapshot.

## Method

* **Commandery seats** (black dots on the user's maps) and **county seats** (open circles) come from CHGIS V5 county points valid 180–230 CE (`research_r6/chgis`). There are 787 points in the area, matched by Chinese name to the Hou Han shu county lists of each commandery c.190. CHGIS has no point for about 45 seats (among them Puyang, Handan, Yuanshi, Lunu, Yingtao, Ganling, Xiling (Jiangxia), Xicheng and most Anping/Hejian counties). For those I used the standard identifications (`r7/commanderies.py` `FALLBACK`). These are accurate to about 5–15 km. Three counties could not be placed at all: 沶鄉 and 安陽 (Hanzhong) and 迺 (Zhuo). The user's map also says Weixing's Weichang and Shangyong's Wu, Anfu and Guangchang are unknown.
* **Hex position**: `geo_hex(lat, lon)` exactly as in `regions_carve6.py` (`rubber.to_world` → `warp.current()` → nearest hex). It round-trips to under 1 km. At these latitudes one hex step is about 2.3 km east–west and 3 km north–south, so **20 walking steps ≈ 45–55 km**.
* **Approximate commandery borders** (red dotted lines in the previews): each land hex belongs to the commandery of its nearest county seat, within 60 km. This is only an estimate. It ignores ridges and rivers, and the Wei-era boundaries on the user's maps differ in detail. It is good enough to say which commandery a region's land and town are on, and how many vanilla-size regions a commandery is worth (median 1060 hexes).
* **Checks on every proposed town** (`r7/check.py`):
  * it is snapped to the nearest passable, non-mountain (blend classes 4–7), non-pass, playable land hex;
  * it is at least 20 steps (walking BFS over passable land and bridges) from every town of the snapshot and of the plan;
  * the region size is estimated with a walking-Voronoi from all proposed towns. This is not a carve: its borders are straight and it ignores rivers and ridges;
  * capital-to-resource walks are measured within each province.
  * **The final plan has no 20-step conflicts.** The smallest gaps are exactly 20: Xuchang–Yangzhai, Dongping–Jibei and Wanxian–Xinye.
* **Names** were checked against `name_registry.json`, both region and province names. A name that is only freed by a rename in this plan counts as free.

## The ten biggest problems (numbers from the snapshot)

1. **Chenjun is about 5× too big, and Runan sits in the wrong place.** Chen state had 9 counties, about 1030 hexes of land. The `3k_main_province_chenjun` province holds **Suiyang 1934 + Ruyang 3406 = 5340 hexes**. All four 190E `chenjun_*` keys together hold **8982 hexes**.
   * Suiyang (the capital) sits on Chen city but carries the name of Liang's seat, 90 km away.
   * Ruyang (3406 hexes, over the vanilla maximum of about 2800) and Peixian (1828) are the real Runan: 45% and 30% of its land.
   * The game's Runan province is on the wrong land. **Ruyin** (1149) is 71% on Jiangxia land. **Pingyu** (2565) is 61% Jiangxia and 30% Nanyang. They are 150–220 km south of the real Ruyin and Pingyu.
2. **Henei has slid north-east onto Dong.** Huaixian is 110 km from Huai; it sits on Baima/Yan, the Baima–Liyang crossing of 200. Zhaoge is 135 km off; it sits on Guantao/Yangping (68% Dong land). Henei's real land is held by Wei's Gongcheng (45% Henei) and by Zhixian.
3. **The Jizhou seats are shifted too.** Ye is 65 km north-east of Ye, on Quliang/Guangping. The Bohai capital "Nanpi" sits on Lecheng (77% Hejian land), 60 km from Nanpi. The r6 Hejian town "Lecheng" landed 40 km south, inside Bohai (56%), and is attached to Pingyuan.
4. **Pei and Pengcheng are swapped around.** The Pengcheng capital is 100% on Pei land, 90 km south-west of Pengcheng. The real Pengcheng lies inside Xiapi's "Farmland" (51% Pengcheng land). No town stands on Xiang (Pei's seat) or on **Qiao** (Cao Cao's home county). "Peixian" is 170 km from Pei county.
5. **The Qingzhou names are wrong.**
   * Beihai's capital "Juxian" (Ju 莒) is 6 hexes from **Linzi**; its land is 76% Qi.
   * "Jimo" sits on Pingshou (Beihai), 90 km from Jimo.
   * The province called **"Taishan" holds Jinan (Dongpingling) + Le'an**. The real Taishan (Fenggao, Mt Tai) has no town.
   * The r6 "Linzi" landed 70 km south-west of Linzi, inside Taishan (65% Taishan land).
6. **Yangzhou's two main cities are wrong.** "Shouchun" is 65 km south of the Huai, on Hefei. The Lujiang capital "Hefei" is 115 km from Hefei, on Lujiang's west. The real Shouchun is inside Fuli, which is itself 100 km from Fuli.
7. **There are duplicate or misleading names.**
   * Anping's "Julu" (83 km off, on Zhao) duplicates the new Julu province.
   * Pengcheng's "Luxian" (Lu 魯, 115 km off) duplicates the new Qufu.
   * "Farmland" is a generic name.
   * The r6 Changshan pair is misplaced. "Zhending" landed 70 km north, on Zhongshan. "Yuanshi" cannot sit on its seat because Yuanshi is 35 km from Yingtao, which is under 20 steps.
8. **The Yanzhou r6 towns fight each other.** Juye is 30 km from Changyi and Chengwu is 32 km from Dingtao, so neither pair can stand on the real sites. "Dongping" is 80 km east of Wuyan, in the Taishan hills. Jibei (Bao Xin) and Liang (Suiyang) have no town. Lu, Rencheng and Dongping are too small to hold separate towns next to Changyi.
9. **The Guangling and Xiapi seats have no town.** Guangling city (the 190 seat; Zhang Chao, Chen Deng) has none: "Jiangdu" is 82 km off near Rugao, and "Gaoyou" sits on Hailing. Xiapi is 45 km south-west of Xiapi.
10. **Nanyang is displaced by 40–45 km.** Wan (Nanyang seat, Battle of Wancheng 197) is 45 km south-east of "Wanxian". Xiangyang is 40 km west of Liu Biao's city; the georef is weak there (see Uncertainty). "Liangxian" actually sits on **Luyang** (Sun Jian and Yuan Shu's base, 190–91).

## Count per zhou

"new" is a new region key. Some new keys only re-occupy a site that a moved region vacates (Dongwuyang, Ruyin, Hefei, Yiyang), so they are not extra land.

| zhou | new (core) | new (optional) | cull | move / move+rename | rename only | province change only |
|---|---|---|---|---|---|---|
| Sili | 0 | 0 | 0 | 2 (+1 opt: Zhixian) | 0 | 0 |
| Yanzhou | 2 (Dongwuyang, Jibei) | 0 | 1 (Juye; +Chengwu in the two-Jiyin variant) | 7 | 0 | 0 |
| Yuzhou | 3 (Yangzhai, Suiyang, Ruyin) | 0 | 0 | 6 | 2 (Luyang, Fengxian) | 0 |
| Yangzhou (Wei) | 1 (Hefei) | 0 | 0 | 1 | 1 (Wancheng) | 0 |
| Qingzhou | 0 | 0 | 0 | 0 | 2 (Linzi, Pingshou) | 1 opt (Buji → Donglai) |
| Xuzhou | 1 (Xuyi) | 0 | 0 | 4 (+1 opt: Tan) | 0 | 0 |
| Jizhou | 2 (Ganling, Yijing) | 1 (Guangping) | 0 | 5 (+1 opt: Lunu) | 3 (Xiangguo, Raoyang, Quyang) | 1 (Changshan → Changshan prov.) |
| Jingzhou (Wei) | 1 (Yiyang) | 2 (Nanxiang, Fangling) | 0 | 1 (+1 opt: Xiangyang) | 1 (Suixian) | 0 |
| **total** | **10** | **3** | **1–2** | **26 (+4 opt)** | **9** | **2** |

Net change: **+9 regions** (+12 with every optional one). Only 6 of these add a commandery that has no town today: Jibei, Liang (Suiyang), the Yingchuan seat, the Xiapi Huai (Xuyi), Qinghe (Ganling) and Hejian's second town (Yijing). The rest put an existing region onto its real commandery.

## Province changes

| province | change |
|---|---|
| `3k_main_province_taishan` | display name "Taishan" → **"Jinan"** (it holds Dongpingling + Lean). This frees "Taishan". |
| **`3k_ironic_province_taishan`** (new) | Fenggao (capital, `ironic_central_qi`), Dongping (`3k_main_dongjun_resource_1`), Jibei (new) |
| `3k_ironic_province_shanyang` | Changyi (capital), Qufu (`ironic_central_luguo`, now attached to Dong), Dingtao (`ironic_central_jiyin`, now attached to Pengcheng; in the other variant, the capital of a Jiyin province that is dissolved) |
| `3k_main_province_dongjun` | Puyang (capital), Dongwuyang (new). It loses Dongping, Qi and Qufu. |
| `3k_main_province_chenjun` | Huaiyang (capital, on Chen), Suiyang (new, Liang). It loses Ruyang. |
| `3k_main_province_runan` | `runan_capital` moves north to **Pingyu**. With it go Langling (`chenjun_resource_2`), Ruyin (new) and Gushi. `runan_resource_1` goes to Jiangxia. The startpos owner of Runan follows the capital key, so check 190E's startpos. |
| `3k_main_province_peixian` | Xiangxian (capital, `chenjun_resource_1` moved) and Qiao (`yangzhou_resource_1` moved). No junction change. |
| `3k_main_province_penchang` | Pengcheng (moved onto its seat) and Fengxian (renamed Luxian) |
| `3k_dlc06_province_xiapi` | Xiapi (moved) and Xuyi (new). "Farmland" becomes Lanling in Donghai. |
| `3k_main_province_yangzhou` (Huainan) | Shouchun (moved onto the Huai), Hefei (new, on the old Shouchun site), Juchao |
| `3k_main_province_lujiang` | Wancheng (renamed "Hefei"), Shuxian, Xunyang |
| `3k_main_province_beihai` | Linzi (renamed Juxian) and Pingshou (renamed Jimo). Optionally move `is_capital` to Pingshou. |
| `3k_main_province_donglai` | + Buji (optional; Buqi was a Donglai county) |
| **`3k_ironic_province_hejian`** (new) | Lecheng (capital, `ironic_central_hejian`; leaves Pingyuan) and Yijing (new) |
| `3k_ironic_province_julu` | Yingtao and Xiangguo (renamed Anping's "Julu"). Xiaquyang/Raoyang goes to Anping. |
| `3k_main_province_anping` | Xindu, Raoyang, Ganling (new, Qinghe) |
| `3k_ironic_province_changshan` | Zhending (Yuanshi moved and renamed) and "Changshan" (from Zhongshan) |
| `3k_main_province_zhongshan` | Lunu and Quyang (the r6 "Zhending" renamed) |
| `3k_main_province_jiangxia` | + Suixian (renamed Runan "Pingyu") and + Yiyang (new, on the Hubei site the Runan capital vacates) |

Every province keeps 2–4 regions. With the optional Nanxiang, Nanyang reaches 4, and Yingchuan is at 4 (Xuchang, Yangzhai, Guandu, Chenliu). Capital-to-resource walks are 20–57 steps (vanilla range 24–60). Dongping–Jibei is 20 and Xuchang–Yangzhai is 20.

## Borders (rivers named on the user's maps)

The walking-Voronoi in the `_after` previews only shows who gets which land. Its borders are straight. When carving, use the cost field of `regions_carve6.py`, which puts borders on rivers and ridges, and these lines:

* **Ji**
  * Zhang river: Wei/Julu and Julu/Anping.
  * Hutuo river: Changshan–Zhongshan and Anping–Hejian.
  * Qing river (Qinghe): Ganling–Xindu.
  * Yellow River (Han course): Pingyuan–Leling.
  * Gu/Yi rivers: Hejian–Zhuo (Yijing lies on the Yi river).
* **Yan**
  * The game's Yellow River: Puyang (south-east bank)–Dongwuyang (north-west bank). The Han city of Puyang was on the south side of the river, which is why the target is 15 km east of the site.
  * Ji river (濟水): Dingtao–Puyang.
  * Wen river (汶水): Dongping/Jibei–Fenggao and Dongping–Qufu.
  * Si river: Qufu–Changyi.
* **Yu**
  * Bian river / Hong canal: Chenliu–Suiyang.
  * Sui river: Suiyang–Qiao.
  * Guo river: Qiao–Huaiyang.
  * Ying river: Xuchang/Yangzhai–Huaiyang and Huaiyang–Pingyu.
  * Ru river: Pingyu–Langling.
  * **Huai**: the whole Runan/Gushi–Jiangxia/Yiyang edge.
* **Xu**
  * Si river: Pengcheng–Xiapi.
  * Yi and Shu rivers: Kaiyang–Tanxian.
  * Sui river (睢水): Xiapi–Xuyi.
  * Huai: Xuyi/Huaiyin–Jiangdu/Hailing.
* **Qing**
  * Ji river: Dongpingling–Lean.
  * Zi river: Linzi–Lean.
  * Wei river (濰水): Pingshou–Dongwu.
  * Jiao river: Pingshou–Changyang/Buji.
* **Sili**: Yellow River (Luoyang/Guandu–Henei), Qin river (Huaixian–Zhixian), Fen river (Pingyang–Anyi).
* **Jing**: Han river (Xiangyang–Xinye, Xiangyang–Suixian), Bai/Yu rivers (Wanxian–Xinye), Dan river (Nanxiang).

## Per-zhou tables

Columns:

* **extent**: hexes of approximate commandery land.
* **current game regions**: the regions covering at least 10% of that land.
* **proposed towns**: the snapped hex and the estimated hexes after the change.
* **Wei-era rows** (*italic*): commanderies created after 190 that appear on the user's maps. They are low priority, because the game starts in 190. Most are already represented by an existing town (noted in the row).

### Yanzhou

| commandery (c.190) | seat → hex | extent | current game regions (share of the commandery's land) | verdict | proposed towns (hex, est. hexes) |
|---|---|---|---|---|---|
| **Dong** | 濮阳 35.70,115.03 → (864,551) | 1707 | Zhaoge [`henei_resource_1`] 35%; Puyang [`dongjun_capital`] 26%; Pingyuan [`pingyuan_capital`] 13%; Huaixian [`henei_capital`] 12% | MOVE capital onto Puyang (south bank); ADD Dongwuyang for the north half (land freed by Henei's Zhaoge/Huaixian) | Puyang *move* (871,548) ~795; Dongwuyang *new* (879,572) ~909 |
| **Jibei** | 卢 36.41,116.63 → (923,575) | 571 | Dongping [`dongjun_resource_1`] 28%; Puyang [`dongjun_capital`] 28%; Dongpingling [`taishan_capital`] 24%; Qufu [`ic_luguo`] 12% | ADD Jibei (Lu 盧) on the site the misplaced r6 Qufu vacates; Taishan province | Jibei *new* (923,575) ~579 |
| **Taishan** | 奉高 36.21,117.39 → (953,566) | 1955 | Linzi [`ic_qi`] 38%; Dongping [`dongjun_resource_1`] 30%; Kaiyang [`langye_resource_1`] 19% | had no town: the r6 'Linzi' already sits here -> MOVE+RENAME to Fenggao; new Taishan province (Fenggao, Jibei, Dongping) | Linzi→Fenggao *move+rename* (945,556) ~880 |
| **Dongping** | 无盐 35.91,116.50 → (919,556) | 426 | Juye [`ic_shanyang_resource_1`] 75%; Qufu [`ic_luguo`] 16% | MOVE 'Dongping' 80 km west onto Wuyan (it sits in the Taishan hills now) | Dongping *move* (921,557) ~815 |
| **Rencheng** | 任城 35.24,116.69 → (928,531) | 211 | Qufu [`ic_luguo`] 80% | too small (3 counties, 35 km from Lu): no town, land to Changyi/Qufu | - |
| **Shanyang** | 昌邑 35.14,116.12 → (907,528) | 995 | Changyi [`ic_shanyang_capital`] 48%; Qufu [`ic_luguo`] 23%; Juye [`ic_shanyang_resource_1`] 19% | MOVE Changyi onto its seat; CULL Juye (30 km from Changyi) | Changyi *move* (907,528) ~763; ~~Juye~~ *cull* |
| **Jiyin** | 定陶 35.09,115.55 → (885,527) | 1188 | Dingtao [`ic_jiyin`] 61%; Puyang [`dongjun_capital`] 20% | MOVE Dingtao onto its seat; CULL Chengwu (32 km from Dingtao); Jiyin joins the Shanyang province | Dingtao *move* (885,527) ~739 |
| **Chenliu** | 陈留 34.67,114.53 → (847,513) | 1636 | Chenliu [`yingchuan_resource_1`] 52%; Guandu [`ic_guandu`] 20%; Suiyang [`chenjun_capital`] 12%; Xuchang [`yingchuan_capital`] 11% | MOVE 45 km south onto Chenliu (stays in Yingchuan province) | Chenliu *move* (848,512) ~1059 |

### Yuzhou

| commandery (c.190) | seat → hex | extent | current game regions (share of the commandery's land) | verdict | proposed towns (hex, est. hexes) |
|---|---|---|---|---|---|
| **Yingchuan** | 阳翟 34.16,113.47 → (805,497) | 2135 | Xuchang [`yingchuan_capital`] 33%; Liangxian [`chenjun_resource_3`] 30%; Ruyang [`chenjun_resource_2`] 25%; Luoyang [`luoyang_capital`] 12% | ADD Yangzhai (Han seat) - one town for 2 regions of land | Xuchang *keep* (823,496) ~969; Yangzhai *new* (803,497) ~686 |
| **Runan** | 平舆 33.16,114.57 → (848,455) | 4853 | Ruyang [`chenjun_resource_2`] 45%; Peixian [`chenjun_resource_1`] 30% | REBUILD: the Runan province moves here from Jiangxia; Runan capital key -> Pingyu, Chenjun's oversize Ruyang -> Langling, new Ruyin on the land Peixian vacates, Gushi stays | Ruyin→Pingyu *move+rename* (849,455) ~1330; Ruyang→Langling *move+rename* (821,441) ~1941; Ruyin *new* (894,443) ~1390; Gushi *keep* (885,417) ~1503 |
| **Chen** | 陈 33.73,114.88 → (861,476) | 1028 | Suiyang [`chenjun_capital`] 68%; Xuchang [`yingchuan_capital`] 32% | SHRINK Chenjun to Chen state: capital MOVE+RENAME 'Suiyang' -> Huaiyang on Chen (1934 -> ~1100 hexes) | Suiyang→Huaiyang *move+rename* (861,476) ~1139 |
| **Liang** | 睢阳 34.45,115.65 → (889,502) | 733 | Suiyang [`chenjun_capital`] 42%; Luxian [`penchang_resource_1`] 35%; Chenliu [`yingchuan_resource_1`] 13% | ADD Suiyang (real Liang seat) - no town today; Chen province | Suiyang *new* (887,502) ~591 |
| **Pei** | 相 33.99,116.79 → (932,483) | 3493 | Pengcheng [`penchang_capital`] 29%; Luxian [`penchang_resource_1`] 19%; Xiapi [`d6_xiapi_capital`] 19%; Peixian [`chenjun_resource_1`] 11% | Pei had no town on Xiang or Qiao: MOVE+RENAME Peixian -> Xiangxian, Fuli -> Qiao; rename Luxian -> Fengxian | Peixian→Xiangxian *move+rename* (932,480) ~1466; Fuli→Qiao *move+rename* (894,480) ~1018; Luxian→Fengxian *rename* (923,508) ~979 |
| **Lu** | 鲁 35.60,116.99 → (939,544) | 461 | Qufu [`ic_luguo`] 54%; Dongping [`dongjun_resource_1`] 39% | MOVE r6 Qufu from Jibei onto Lu; Shanyang province | Qufu *move* (938,542) ~817 |
| *Qiao* (Wei-era; Wei 220, from Pei; Cao Cao's home county) | 谯 33.88,115.77 → (894,480) | - | Suiyang [`chenjun_capital`] | Qiao region (Cao Cao's home) - see Pei | - |
| *Yiyang* (Wei-era; Wei-era, from Runan / Jiangxia) | 弋阳 32.17,115.00 → (864,418) | - | Ruyang [`chenjun_resource_2`] | Gushi + the new Hubei 'Yiyang' cover it | - |

### Yangzhou (Wei part)

| commandery (c.190) | seat → hex | extent | current game regions (share of the commandery's land) | verdict | proposed towns (hex, est. hexes) |
|---|---|---|---|---|---|
| **Jiujiang (Huainan)** | 寿春 32.58,116.78 → (928,430) | 3216 | Shouchun [`yangzhou_capital`] 40%; Juchao [`yangzhou_resource_3`] 19%; Fuli [`yangzhou_resource_1`] 12% | MOVE Shouchun 65 km north onto the Huai; ADD Hefei on the old Shouchun site | Shouchun *move* (930,427) ~1694; Hefei *new* (937,407) ~1269 |
| **Lujiang** | 舒 31.19,117.17 → (931,384) | 4219 | Hefei [`lujiang_capital`] 38%; Gushi [`yangzhou_resource_2`] 21%; Shuxian [`lujiang_resource_2`] 12%; Juchao [`yangzhou_resource_3`] 11% | RENAME the misplaced 'Hefei' (Lujiang capital, 115 km off) to Wancheng | Hefei→Wancheng *rename* (902,381) ~1580; Juchao *keep* (943,388) ~1177; Shuxian *keep* (905,354) ~1132 |
| *Anfeng* (Wei-era; Wei-era, from Lujiang) | 安丰 32.35,116.30 → (910,422) | - | Fuli [`yangzhou_resource_1`] | no town; split between Gushi, Shouchun, Wancheng (Wei-era, low priority) | - |

### Qingzhou

| commandery (c.190) | seat → hex | extent | current game regions (share of the commandery's land) | verdict | proposed towns (hex, est. hexes) |
|---|---|---|---|---|---|
| **Jinan** | 东平陵 36.71,117.52 → (956,585) | 856 | Dongpingling [`taishan_capital`] 62%; Lean [`taishan_resource_1`] 21%; Pingyuan [`pingyuan_capital`] 15% | keep Dongpingling; province 3k_main_province_taishan displays 'Jinan' | Dongpingling *keep* (950,581) ~1062 |
| **Le'an** | 临济 37.10,117.95 → (972,599) | 890 | Lean [`taishan_resource_1`] 53%; Leling [`pingyuan_resource_1`] 21%; Jimo [`beihai_resource_1`] 13%; Juxian [`beihai_capital`] 11% | keep Lean | Lean *keep* (990,605) ~554 |
| **Qi** | 临淄 36.86,118.37 → (988,590) | 691 | Juxian [`beihai_capital`] 64%; Jimo [`beihai_resource_1`] 14%; Linzi [`ic_qi`] 13% | RENAME Beihai's 'Juxian' (6 hexes from Linzi) -> Linzi | Juxian→Linzi *rename* (989,584) ~1236 |
| **Beihai** | 剧 36.66,118.78 → (1004,581) | 1812 | Jimo [`beihai_resource_1`] 55%; Buji [`langye_resource_2`] 19%; Changyang [`donglai_resource_1`] 17% | RENAME 'Jimo' -> Pingshou (it sits on Pingshou); make it the Beihai capital | Jimo→Pingshou *rename* (1022,578) ~1291 |
| **Donglai** | 黄 37.65,120.52 → (1067,614) | 2773 | Changyang [`donglai_resource_1`] 72%; Huangxian [`donglai_capital`] 21% | keep; Buji -> Donglai province (optional) | Buji *keep (opt)* (1060,570) ~820; Huangxian *keep* (1041,614) ~861; Changyang *keep* (1088,591) ~1647 |
| *Chengyang* (Wei-era; Wei-era (Dongwu), from Langya/Beihai) | 东武 35.99,119.40 → (1029,555) | - | Dongwu [`langye_capital`] | = Dongwu (Langya capital), keep | - |
| *Dongguan* (Wei-era; Wei-era, from Langya) | 东莞 35.79,118.62 → (1000,549) | - | Kaiyang [`langye_resource_1`] | no town (Wei-era; Yi valley between Kaiyang and Linzi) - skip | - |

### Xuzhou

| commandery (c.190) | seat → hex | extent | current game regions (share of the commandery's land) | verdict | proposed towns (hex, est. hexes) |
|---|---|---|---|---|---|
| **Langya** | 开阳 35.15,118.39 → (992,526) | 2441 | Dongwu [`langye_capital`] 41%; Kaiyang [`langye_resource_1`] 34%; Linzi [`ic_qi`] 10% | keep Dongwu + Kaiyang | Dongwu *keep* (1033,552) ~1126; Kaiyang *keep* (990,531) ~1597 |
| **Donghai** | 郯 34.60,118.35 → (990,505) | 1733 | Tanxian [`donghai_capital`] 47%; Farmland [`d6_xiapi_resource_1`] 18%; Kaiyang [`langye_resource_1`] 13%; Haixi [`donghai_resource_1`] 12% | MOVE Tan 25 km (opt); 'Farmland' MOVE+RENAME -> Lanling (west Donghai) | Farmland→Lanling *move+rename* (966,513) ~916; Tanxian *move (opt)* (990,505) ~1299 |
| **Pengcheng** | 彭城 34.27,117.19 → (947,493) | 799 | Farmland [`d6_xiapi_resource_1`] 82%; Xiapi [`d6_xiapi_capital`] 17% | MOVE Pengcheng 90 km NE onto its seat (Farmland vacates it) | Pengcheng *move* (947,493) ~633 |
| **Xiapi** | 下邳 34.12,117.89 → (973,487) | 3263 | Huaiyin [`guangling_capital`] 34%; Xiapi [`d6_xiapi_capital`] 34%; Haixi [`donghai_resource_1`] 17%; Tanxian [`donghai_capital`] 13% | MOVE Xiapi 45 km NE onto its seat; ADD Xuyi for the Huai (Liu Bei vs Yuan Shu 196) | Xiapi *move* (973,487) ~1085; Xuyi *new* (989,454) ~1941; Huaiyin *keep* (1015,449) ~1565 |
| **Guangling** | 广陵 32.39,119.44 → (1021,423) | 4317 | Gaoyou [`guangling_resource_1`] 33%; Haixi [`donghai_resource_1`] 32%; Huaiyin [`guangling_capital`] 19% | MOVE Jiangdu onto Guangling/Jiangdu (190 seat); RENAME Gaoyou -> Hailing | Haixi *keep* (1061,478) ~1437; Jiangdu *move* (1021,421) ~1043; Gaoyou→Hailing *move+rename* (1046,424) ~2144 |

### Sili

| commandery (c.190) | seat → hex | extent | current game regions (share of the commandery's land) | verdict | proposed towns (hex, est. hexes) |
|---|---|---|---|---|---|
| **Henan** | 雒阳 34.73,112.60 → (765,519) | 1619 | Guandu [`ic_guandu`] 40%; Luoyang [`luoyang_capital`] 40% | keep Luoyang + Guandu | Luoyang *keep* (784,517) ~1300; Guandu *keep* (825,517) ~619 |
| **Henei** | 怀 35.09,113.33 → (799,529) | 2362 | Gongcheng [`weijun_resource_1`] 38%; Zhixian [`d6_shangdang_resource_2`] 29%; Huaixian [`henei_capital`] 25% | MOVE Huaixian (110 km off) and Zhaoge (135 km off) back north of the Yellow River onto Henei; Zhixian optional | Huaixian *move* (803,530) ~732; Zhaoge *move* (830,547) ~953; Zhixian *move (opt)* (765,531) ~862 |
| **Hongnong** | 弘农 34.66,110.93 → (707,520) | 2518 | Hongnong [`luoyang_resource_1`] 55%; Luoyang [`luoyang_capital`] 24%; Liangxian [`chenjun_resource_3`] 12% | keep | Hongnong *keep* (677,516) ~2115 |
| **Hedong** | 安邑 35.18,111.16 → (713,534) | 6324 | Pingyang [`d6_hedong_resource_2`] 28%; Zhangzi [`shangdang_capital`] 26% | keep (Anyi can't reach its seat: Qi Pass within 20 steps) | Anyi *keep* (688,541) ~1372; Puzhou *keep* (660,532) ~477; Pingyang *keep* (701,565) ~1583 |
| *Pingyang* (Wei-era; Wei 225, from Hedong) | 平阳 36.06,111.42 → (718,566) | - | Pingyang [`d6_hedong_resource_2`] | = Pingyang (hedong_resource_2), keep | - |

### Jingzhou (Wei part)

| commandery (c.190) | seat → hex | extent | current game regions (share of the commandery's land) | verdict | proposed towns (hex, est. hexes) |
|---|---|---|---|---|---|
| **Nanyang** | 宛 33.00,112.53 → (768,456) | 7628 | Wanxian [`nanyang_capital`] 25%; Xinye [`nanyang_resource_1`] 23%; Xiangyang [`xiangyang_capital`] 13%; Liangxian [`chenjun_resource_3`] 11%; Pingyu [`runan_resource_1`] 10% | MOVE Wanxian onto Wan; RENAME Liangxian -> Luyang; Nanxiang optional | Liangxian→Luyang *rename* (781,485) ~1944; Wanxian *move* (768,455) ~1275; Xinye *keep* (770,436) ~946; Nanxiang *new (opt)* (724,458) ~2950 |
| *Nanxiang* (Wei-era; Wei 208+, from Nanyang) | 南乡 32.96,111.36 → (720,459) | - | Wanxian [`nanyang_capital`] | optional new region (Dan valley) | - |
| **Nan** | 江陵 30.35,112.19 → (773,368) | 5189 | Huarong [`jingzhou_resource_1`] 28%; linju [`xiangyang_resource_1`] 21%; Jiangling [`jingzhou_capital`] 16%; Yong'an [`badong_capital`] 11% | Xiangyang move optional (georef weak; keep on the Han's south bank) | Xiangyang *move (opt)* (758,422) ~1546 |
| *Xiangyang* (Wei-era; Cao Cao 208, from Nan / Nanyang) | 襄阳 32.03,112.16 → (758,422) | - | Xinye [`nanyang_resource_1`] | = Xiangyang (keep / optional move) | - |
| **Jiangxia** | 西陵 30.60,114.80 → (856,368) | 5307 | Pingyu [`runan_resource_1`] 29%; Ruyin [`runan_capital`] 15%; Xiyang [`jiangxia_resource_1`] 15%; Xiling [`jiangxia_capital`] 14%; Huarong [`jingzhou_resource_1`] 11% | the misplaced Runan pair become Jiangxia: RENAME Pingyu -> Suixian; ADD Yiyang on the vacated Runan-capital site | Pingyu→Suixian *rename* (798,401) ~1751; Yiyang *new* (848,401) ~1542 |
| **Hanzhong (east: Xicheng/Shangyong/Fangling)** | 西城 32.70,109.03 → (625,453) | 5276 | Xicheng [`shangyong_resource_1`] 29%; linju [`xiangyang_resource_1`] 26%; Shangyong [`shangyong_capital`] 17%; Xiangyang [`xiangyang_capital`] 15% | keep Xicheng (= Wei Weixing) + Shangyong; Fangling optional | Fangling *new (opt)* (701,427) ~1604 |
| *Xincheng* (Wei-era; 220, Fangling) | 房陵 32.06,110.73 → (701,427) | - | Xiangyang [`xiangyang_capital`] | optional Fangling | - |
| *Shangyong* (Wei-era; 215, from Hanzhong) | 上庸 32.30,110.20 → (677,437) | - | Shangyong [`shangyong_capital`] | = Shangyong, keep | - |
| *Weixing* (Wei-era; 220, Xicheng) | 西城 32.70,109.03 → (625,453) | - | Xicheng [`shangyong_resource_1`] | = Xicheng, keep | - |

### Jizhou

| commandery (c.190) | seat → hex | extent | current game regions (share of the commandery's land) | verdict | proposed towns (hex, est. hexes) |
|---|---|---|---|---|---|
| **Wei** | 邺 36.27,114.41 → (838,573) | 2304 | Ye [`weijun_capital`] 35%; Gongcheng [`weijun_resource_1`] 33%; Julu [`anping_resource_1`] 13%; Zhaoge [`henei_resource_1`] 11% | MOVE Ye 65 km SW onto Ye; Gongcheng MOVE+RENAME -> Linlu (clears Ye) | Ye *move* (838,573) ~830; Gongcheng→Linlu *move+rename* (817,566) ~920 |
| **Zhao** | 邯郸 36.60,114.48 → (840,585) | 625 | Julu [`anping_resource_1`] 55%; Yingtao [`ic_julu_capital`] 25%; Gongcheng [`weijun_resource_1`] 12% | RENAME Anping's 'Julu' -> Xiangguo (it sits on Zhao); Julu province | Julu→Xiangguo *rename* (822,606) ~1362 |
| **Changshan** | 元氏 37.77,114.53 → (837,626) | 1602 | Yuanshi [`ic_changshan_capital`] 37%; Changshan [`zhongshan_resource_1`] 22%; Yingtao [`ic_julu_capital`] 20%; Zhending [`ic_changshan_resource_1`] 10% | Yuanshi is 35 km from Yingtao: MOVE+RENAME it -> Zhending; 190E 'Changshan' joins the province | Yuanshi→Zhending *move+rename* (836,638) ~642; Changshan *keep* (802,645) ~1395 |
| **Zhongshan** | 卢奴 38.52,114.98 → (852,652) | 2414 | Lunu [`zhongshan_capital`] 24%; Gaoliu [`daijun_capital`] 20%; Zhending [`ic_changshan_resource_1`] 19%; Fanyang [`ic_zhuo_resource_1`] 15%; Fanzhi [`yanmen_resource_1`] 11% | RENAME r6 'Zhending' (70 km off) -> Quyang, Zhongshan province; Lunu move optional | Zhending→Quyang *rename* (827,661) ~700; Lunu *move (opt)* (852,652) ~605 |
| **Hejian** | 乐成 38.15,116.21 → (902,638) | 1695 | Zhangwu [`bohai_resource_1`] 36%; Nanpi [`bohai_capital`] 28%; Zhuo [`ic_zhuo_capital`] 18% | MOVE Lecheng onto its seat (Nanpi town sits there); ADD Yijing; own Hejian province | Lecheng *move* (898,640) ~735; Yijing *new* (895,662) ~800 |
| **Bohai** | 南皮 38.04,116.70 → (921,634) | 915 | Lecheng [`ic_hejian`] 57%; Zhangwu [`bohai_resource_1`] 41% | MOVE Nanpi 60 km east onto its seat | Nanpi *move* (921,634) ~674; Zhangwu *keep* (930,651) ~550 |
| **Anping** | 信都 37.57,115.56 → (879,618) | 1420 | Xindu [`anping_capital`] 36%; Xiaquyang [`ic_julu_resource_1`] 30%; Lecheng [`ic_hejian`] 16% | keep Xindu; RENAME r6 'Xiaquyang' (on Anping) -> Raoyang, Anping province | Xindu *keep* (867,617) ~761; Xiaquyang→Raoyang *rename* (870,638) ~651 |
| **Julu** | 廮陶 37.62,114.92 → (853,620) | 884 | Yingtao [`ic_julu_capital`] 41%; Ye [`weijun_capital`] 40%; Xiaquyang [`ic_julu_resource_1`] 11% | keep Yingtao | Guangping *new (opt)* (856,589) ~769; Yingtao *keep* (845,620) ~606 |
| **Qinghe** | 甘陵 36.93,115.72 → (887,595) | 583 | Ye [`weijun_capital`] 54%; Pingyuan [`pingyuan_capital`] 29% | ADD Ganling (fills the gap Ye leaves) | Ganling *new* (887,595) ~951 |
| **Pingyuan** | 平原 37.02,116.44 → (914,598) | 1922 | Leling [`pingyuan_resource_1`] 45%; Pingyuan [`pingyuan_capital`] 40% | keep Pingyuan + Leling (Lecheng leaves the province) | Pingyuan *keep* (919,608) ~1147; Leling *keep* (952,620) ~1179 |
| *Guangping* (Wei-era; Wei-era, from Julu/Zhao/Wei (Quliang)) | 曲梁 36.73,114.95 → (858,589) | - | Ye [`weijun_capital`] | optional new on the old Ye site | - |
| *Yangping* (Wei-era; created 213-220 from Dong + Wei) | 馆陶 36.52,115.32 → (873,581) | - | Zhaoge [`henei_resource_1`] | = Dongwuyang (new) | - |
| *Leling* (Wei-era; Wei-era, from Pingyuan (seat Yanci)) | 厌次 37.55,117.33 → (947,616) | - | Leling [`pingyuan_resource_1`] | = Leling, keep | - |

## Name-clash check

* **No proposed name clashes** with a region or province name in `name_registry.json` (checked by `r7/build_json.py`).
* **Names reused after being freed.** Each of these is freed by a rename or move in the same plan:
  * **Suiyang**: Chen's capital becomes Huaiyang.
  * **Pingyu** and **Ruyin**: the Hubei Runan pair become Suixian and Yiyang.
  * **Hefei**: the Lujiang capital becomes Wancheng.
  * **Zhending**: the r6 region becomes Quyang.
* **Vanilla convention.** A region may share its own province's name (Luoyang, Xiangyang), but this proposal avoids doing so. That is why the Chen capital becomes **Huaiyang** (Chen was the Huaiyang kingdom until 88 CE; the city is Huaiyang today) rather than "Chen". Alternative: "Wanqiu".
* **Look-alike names** (edit distance ≤ 1, flagged for the user):
  * **Langling** (Runan) / **Lanling** (Donghai). If they are too close, rename Lanling to **Changlü** (Zang Ba's Changlü, 30 km west).
  * **Luyang** / **Luoyang**. Both are historical, and Luyang is exactly where the region's town sits. The alternative is to keep "Liangxian".
  * **Quyang** / **Puyang**. Alternative: "Shangquyang".
  * **Yiyang** (Jiangxia) / **Xiyang** (the existing Jiangxia resource). Alternative: "Qisi" or "Meng".
  * Minor: Ganling / Wanling, Linlu / Linyu / linju, Ruyin / Tuyin, Pingyu / Pingyi.
* **Single-syllable county names** take the 190E "-xian" form (Xiangxian 相, Fengxian 豐), as with Wanxian, Huaixian and Tanxian.

## Uncertainty / caveats

* **The south is weakly georeferenced.** The south half of the map is not stretched, and 190E compresses the Yangtze band: the game's Yangtze at Wuhan is about 20 rows north of the georef. From Jiangling to Hefei, seats come out 0.3–0.5° off the game's rivers. So:
  * **Xiangyang's move is optional.** The georef target is east of the river the current town sits beside. Only move it if it stays on the Han's south bank.
  * Shouchun, Hefei, Yiyang and Suixian should be sited against the game's Huai and Han, not blindly on lat/lon.
* **Approximate borders only.** The commandery extents are a nearest-county estimate. The user's maps are Wei-era (c.220–230), with Yangping, Guangping, Leling, Qiao, Yiyang, Anfeng, Chengyang, Dongguan, Pingyang, Nanxiang, Xiangyang, Xincheng, Shangyong and Weixing, and Pingyuan counted in Jizhou. The game starts in 190, so the tables are keyed to the Han 190 units and list the Wei units as rows.
* **Seats not located** in CHGIS; standard identifications were used instead: Puyang, Handan, Yuanshi, Lunu, Yingtao, Ganling, Xiling, Xicheng, Juancheng area (CHGIS has 鄄城 only for Wei), and several Anping/Hejian/Changshan counties. Some Han-era identifications are disputed:
  * Juchao: CHGIS puts it at Tongcheng; the usual identification is Chaohu.
  * Xiling (Jiangxia seat).
  * Langling.
* **The r6 carve is still running.** The r6 new regions (Qufu, Changyi, Juye, Jiyin) changed between two snapshots taken 10 minutes apart. The plan names targets, so it holds whichever variant lands. `plan.py` accepts `a|b` keys, and the cull of Chengwu only applies to the variant that has it.
* **Estimated hexes are rough.** "est. hexes" is a walking-Voronoi that counts impassable land too. So Nanxiang (~2950) and Hailing (~2140) look big: they absorb mountains or coast that a real carve would share differently. Treat these as ±30%.
* **Anyi stays 55 km from its seat.** The real Anyi is under 20 steps from Qi Pass, and passes are untouched.
* **Luoyang is kept** about 28 km east of the Han city; moving it gains little.
* **Startpos.** Moving capital keys (`runan_capital`, `chenjun_resource_1` for Pei, `weijun_capital`, `henei_capital`, `dongjun_capital`, `penchang_capital`) keeps each faction's 190 holdings on the right commandery. Ownership in `startpos` is keyed by region, so re-check who owns the re-keyed Hubei sites (Suixian, Yiyang).

## Files

* `research/main190/research_r6/candidates_r7.json`: new regions (`provinces`), edits to existing regions (`changes`, with `target` lat/lon, `target_hex`, `est_hexes` and new `province`), province creations and renames, `name_clashes` (empty) and `similar_names`.
* `research/main190/previews/r7_proposal_{yan_yu_yang,qing_xu,sili,jing_wei,ji}.png`: the current regions with the proposal overlaid.
* `research/main190/previews/r7_proposal_*_after.png`: the estimated result.
* `research/main190/research_r6/r7/`:
  * `plan.py`: the proposal source of truth.
  * `check.py`: validation.
  * `commanderies.py` / `commanderies.json`: seats and counties.
  * `seats.json`: seats placed on hexes.
  * `extent.py` / `han_extent.npy`: commandery extents.
  * `render.py`, `build_json.py`, `gen_tables.py`.
  * `map_snapshot.hex`: the map state used.
