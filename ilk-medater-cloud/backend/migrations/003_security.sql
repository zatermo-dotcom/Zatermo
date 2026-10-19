-- Règles de sécurité appliquées par la base elle-même (défense en profondeur).
-- 1. Journal d'audit : ajout uniquement via audit_append(), chaînage SHA-256, aucune modification/suppression.
-- 2. Autorisations et réglages IA : seul le Directeur général actif peut créer ou modifier (trigger).
-- 3. Rôle applicatif ilk_app : aucun DELETE, aucun accès en écriture au journal, ne peut pas créer de Directeur.

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ilk_app') THEN
    RAISE EXCEPTION 'Le rôle ilk_app doit exister avant la migration (voir docker/db-init/01-roles.sh).';
  END IF;
END $$;

-- ---------------------------------------------------------------- Audit
CREATE FUNCTION audit_payload(p_prev text, p_at timestamptz, p_actor int, p_action text, p_resource text,
                              p_company int, p_details jsonb, p_ip text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
  SELECT concat_ws('|', p_prev, to_char(p_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US'),
                   coalesce(p_actor::text,'-'), p_action, p_resource, coalesce(p_company::text,'-'),
                   p_details::text, coalesce(p_ip,'-'))
$$;

CREATE FUNCTION audit_append(p_actor int, p_action text, p_resource text, p_company int, p_details jsonb, p_ip text)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_prev text; v_at timestamptz := clock_timestamp(); v_hash text; v_id bigint;
BEGIN
  PERFORM pg_advisory_xact_lock(424242);
  SELECT hash INTO v_prev FROM audit_events ORDER BY id DESC LIMIT 1;
  v_prev := coalesce(v_prev, 'GENESIS');
  v_hash := encode(digest(audit_payload(v_prev, v_at, p_actor, p_action, coalesce(p_resource,''), p_company,
                                         coalesce(p_details,'{}'::jsonb), p_ip), 'sha256'), 'hex');
  INSERT INTO audit_events(at, actor_id, action, resource, company_id, details, ip, prev_hash, hash)
  VALUES (v_at, p_actor, p_action, coalesce(p_resource,''), p_company, coalesce(p_details,'{}'::jsonb), p_ip, v_prev, v_hash)
  RETURNING id INTO v_id;
  RETURN v_id;
END $$;

-- Renvoie le premier événement dont le chaînage est rompu (aucune ligne = journal intègre).
CREATE FUNCTION audit_verify() RETURNS TABLE(broken_id bigint, reason text)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE r record; v_prev text := 'GENESIS';
BEGIN
  FOR r IN SELECT * FROM audit_events ORDER BY id LOOP
    IF r.prev_hash <> v_prev THEN broken_id := r.id; reason := 'prev_hash'; RETURN NEXT; RETURN; END IF;
    IF r.hash <> encode(digest(audit_payload(r.prev_hash, r.at, r.actor_id, r.action, r.resource, r.company_id, r.details, r.ip), 'sha256'), 'hex') THEN
      broken_id := r.id; reason := 'hash'; RETURN NEXT; RETURN;
    END IF;
    v_prev := r.hash;
  END LOOP;
END $$;

CREATE FUNCTION audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Le journal d''audit est en ajout seul (% interdit)', TG_OP; END $$;
CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION audit_immutable();
CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION audit_immutable();

-- ---------------------------------------------------------------- Règle absolue : seul le DG attribue les droits
CREATE FUNCTION is_active_director(p_user int) RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT EXISTS (SELECT 1 FROM users WHERE id = p_user AND is_group_director AND enabled)
$$;

CREATE FUNCTION enforce_director_grant() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT is_active_director(NEW.changed_by) OR (TG_OP = 'INSERT' AND NOT is_active_director(NEW.granted_by)) THEN
    RAISE EXCEPTION 'Seul le Directeur général du groupe peut attribuer ou modifier une autorisation';
  END IF;
  IF EXISTS (SELECT 1 FROM users WHERE id = NEW.user_id AND is_group_director) THEN
    RAISE EXCEPTION 'Le Directeur général dispose déjà de tous les droits';
  END IF;
  IF TG_OP = 'UPDATE' AND (NEW.user_id <> OLD.user_id OR NEW.scope_type <> OLD.scope_type OR NEW.scope_ref <> OLD.scope_ref
                           OR NEW.company_id IS DISTINCT FROM OLD.company_id OR NEW.granted_by <> OLD.granted_by) THEN
    RAISE EXCEPTION 'Le périmètre d''une autorisation ne se modifie pas : révoquer puis en créer une nouvelle';
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status = 'revoked' THEN
    RAISE EXCEPTION 'Une autorisation révoquée est définitive';
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER grants_director_only BEFORE INSERT OR UPDATE ON grants FOR EACH ROW EXECUTE FUNCTION enforce_director_grant();

CREATE FUNCTION enforce_director_ai() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT is_active_director(NEW.updated_by) THEN
    RAISE EXCEPTION 'Seul le Directeur général du groupe peut activer ou désactiver l''IA';
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER ai_settings_director_only BEFORE INSERT OR UPDATE ON ai_settings FOR EACH ROW EXECUTE FUNCTION enforce_director_ai();

-- Empêche la promotion d'un compte en Directeur par l'application (seule la CLI propriétaire peut le faire).
CREATE FUNCTION protect_director_flag() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (TG_OP = 'INSERT' AND NEW.is_group_director) OR (TG_OP = 'UPDATE' AND NEW.is_group_director IS DISTINCT FROM OLD.is_group_director) THEN
    IF current_user = 'ilk_app' THEN
      RAISE EXCEPTION 'Le statut de Directeur général ne peut pas être attribué par l''application';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER users_protect_director BEFORE INSERT OR UPDATE ON users FOR EACH ROW EXECUTE FUNCTION protect_director_flag();

-- ---------------------------------------------------------------- Privilèges du rôle applicatif
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO ilk_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ilk_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ilk_app;

GRANT INSERT (email, full_name, job_title, org_unit_code, password_hash, enabled, must_change_password, mfa_secret_enc,
              locked_until, password_changed_at, last_login_at) ON users TO ilk_app;
GRANT UPDATE (full_name, job_title, org_unit_code, password_hash, enabled, mfa_enabled, mfa_secret_enc, failed_logins,
              locked_until, must_change_password, password_changed_at, last_login_at) ON users TO ilk_app;
GRANT INSERT, UPDATE ON recovery_codes, sessions, grants, ai_settings, ai_consents, ai_requests,
  parties, projects, milestones, sites, site_daily_reports, site_risks, contracts, contract_events, situations,
  invoices, payments, purchase_orders, stock_items, stock_movements, equipment, employees, leave_requests,
  qhse_events, documents, document_versions, deliverables, calc_runs, coordination_issues, legal_sources TO ilk_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_events FROM ilk_app;
REVOKE EXECUTE ON FUNCTION audit_append(int,text,text,int,jsonb,text), audit_verify() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION audit_append(int,text,text,int,jsonb,text), audit_verify() TO ilk_app;
