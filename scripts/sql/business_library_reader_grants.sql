-- 可审查授权模板：由管理员先创建专用 LOGIN 账号并使用本机安全渠道设置密码。
-- 此处只创建可继承的 NOLOGIN 只读角色，不创建密码或修改现有运行账号。
BEGIN;
CREATE ROLE market_library_readonly NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
GRANT USAGE ON SCHEMA public,document_review,business_library TO market_library_readonly;
GRANT SELECT ON public.mr_kb_versions,public.mr_document_versions,public.mr_kb_documents,
 public.mr_release_history,public.mr_active,document_review.documents TO market_library_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA business_library TO market_library_readonly;
-- 管理员另行审核 GRANT market_library_readonly TO <专用登录账号>，不授予写入或DDL权限。
COMMIT;
