# 2026-11-13 首批处罚案例接收

用户授权接收指定案例目录。目录共2814个文件，PDF/DOCX各1407个；本批只选20份有效、不重复的PDF，避免同时将配套Word/PDF机械计为双份资料。

已真实接收20份PDF、84页，管理员数据域admin-import，批次case-import-ah-20261113。原文、页、原件SHA及稳定source_file_id/parse_id/doc_version_id均保留；PostgreSQL追加20条解析与20条case目录、20条空case_profiles。正式审核事件、KB版本和ACTIVE不变。

标题仅是原文件名的未核验显示标题。案号、地区、机关、日期、违法事实、处罚类型、金额、结果及法律引用未可靠确认，结构字段保持NULL，field_sources为空，verification_status=pending。原文可供人工复核，不将OCR或目录名称当作事实核验。

当前共有117条法规目录与20条案例目录，均未索引/未发布；默认法规/案例页面仍遵循ACTIVE空态。原121条解析、117条法规关联与ACTIVE逐项核对不变；本批原文件只读，副本通过SHA校验。未搬迁原始文件或修改SQLite历史任务。

接收前已按正式交付要求备份PostgreSQL、MySQL审核库和状态文件（SQLite采用backup API）；备份仅在本机ignored目录。接收包装首次缺少模块搜索路径，未写入数据库；修正环境后完成，未把失败算成功。

真实PG回归验证案例接收幂等、类型隔离、未知结构字段为NULL及不创建KB成员。此为Agent C自测和授权资料接收，不是独立QA或案例法律结论。

含真实名称/正文的manifest、解析JSON、接收回执仅保存在本机ignored local/case-import-ah-20261113/，不进Git。后续需人工核验，不自动将这批案例纳入正式发布。
