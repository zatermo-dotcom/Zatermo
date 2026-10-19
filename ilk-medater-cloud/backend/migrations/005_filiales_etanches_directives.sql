-- Décision de la Direction : eurl medater et cabinet ILK ont une gestion entièrement séparée, de A à Z.
-- * Seule la Direction générale a accès aux informations des deux filiales.
-- * Tout autre intervenant est rattaché à UNE filiale ; ses autorisations ne peuvent viser que cette filiale.
-- * Plus aucun service commun n'ouvre de données : RH et juridique sont dédoublés par filiale.
-- * La Direction générale émet des directives, suivies projet par projet.

-- ---------------------------------------------------------------- Rattachement des comptes à une filiale
ALTER TABLE users ADD COLUMN company_id int REFERENCES companies(id);

-- Reprise de l'existant : filiale du département du compte, sinon filiale unique de ses autorisations actives.
UPDATE users u SET company_id = c.id
  FROM org_units o JOIN companies c ON c.code = o.company_code
 WHERE u.org_unit_code = o.code AND NOT u.is_group_director;
UPDATE users u SET company_id = sub.cid
  FROM (SELECT user_id, min(company_id) AS cid FROM grants WHERE status = 'active' AND company_id IS NOT NULL
        GROUP BY user_id HAVING count(DISTINCT company_id) = 1) sub
 WHERE u.id = sub.user_id AND u.company_id IS NULL AND NOT u.is_group_director;

-- ---------------------------------------------------------------- Plus de service commun porteur de données
INSERT INTO org_units (code, parent_code, company_code, name, kind, floor, modules, sort) VALUES
 ('ARCH-HR', 'ARCH', 'ARCH', 'Ressources humaines du cabinet', 'service', 2, '{hr}', 44);

UPDATE org_units SET active = false, modules = '{}' WHERE code IN ('SHARED-HR', 'SHARED-LEGAL');
-- Le bureau de la Direction générale reste celui du seul Directeur : il n'ouvre rien par autorisation.
UPDATE org_units SET modules = '{}' WHERE code = 'SHARED-EXEC';
UPDATE users SET org_unit_code = NULL
 WHERE org_unit_code IN ('SHARED-HR', 'SHARED-LEGAL', 'SHARED-FIN') AND NOT is_group_director;

-- Révocation des autorisations devenues contraires à la règle (traçabilité conservée) :
-- services communs supprimés, ou autorisation hors de la filiale du compte.
UPDATE grants g SET status = 'revoked', revoked_at = now(), changed_by = (SELECT id FROM users WHERE is_group_director)
 WHERE g.status <> 'revoked'
   AND EXISTS (SELECT 1 FROM users WHERE is_group_director AND enabled)
   AND ((g.scope_type = 'org_unit' AND g.scope_ref IN ('SHARED-HR', 'SHARED-LEGAL', 'SHARED-EXEC', 'SHARED-FIN'))
        OR g.company_id IS DISTINCT FROM (SELECT company_id FROM users WHERE id = g.user_id));

-- Défense en base : une autorisation vise obligatoirement la filiale de rattachement du compte.
CREATE FUNCTION enforce_grant_same_company() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status <> 'revoked' AND (NEW.company_id IS NULL OR NEW.company_id IS DISTINCT FROM
       (SELECT company_id FROM users WHERE id = NEW.user_id)) THEN
    RAISE EXCEPTION 'Filiales séparées : une autorisation ne peut viser que la filiale de rattachement du collaborateur';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER grants_same_company BEFORE INSERT OR UPDATE ON grants FOR EACH ROW EXECUTE FUNCTION enforce_grant_same_company();

-- Changer la filiale d'un compte n'est possible que s'il n'a plus aucune autorisation active.
CREATE FUNCTION protect_user_company() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.company_id IS DISTINCT FROM OLD.company_id
     AND EXISTS (SELECT 1 FROM grants WHERE user_id = NEW.id AND status <> 'revoked') THEN
    RAISE EXCEPTION 'Révoquer les autorisations du collaborateur avant de changer sa filiale de rattachement';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER users_protect_company BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION protect_user_company();

GRANT INSERT (company_id), UPDATE (company_id) ON users TO ilk_app;

-- ---------------------------------------------------------------- Directives de la Direction générale
CREATE TABLE directives (
  id            serial PRIMARY KEY,
  company_id    int NOT NULL REFERENCES companies(id),
  project_id    int NOT NULL REFERENCES projects(id),
  title         text NOT NULL,
  instructions  text NOT NULL,
  priority      text NOT NULL DEFAULT 'normale' CHECK (priority IN ('normale','haute','urgente')),
  due_date      date,
  status        text NOT NULL DEFAULT 'emise' CHECK (status IN ('emise','accusee','en_cours','realisee','cloturee','annulee')),
  issued_by     int NOT NULL REFERENCES users(id),
  issued_at     timestamptz NOT NULL DEFAULT now(),
  closed_by     int REFERENCES users(id),
  closed_at     timestamptz,
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX directives_project ON directives(project_id);

CREATE TABLE directive_updates (
  id            serial PRIMARY KEY,
  directive_id  int NOT NULL REFERENCES directives(id),
  company_id    int NOT NULL REFERENCES companies(id),
  author_id     int NOT NULL REFERENCES users(id),
  note          text NOT NULL,
  new_status    text CHECK (new_status IN ('emise','accusee','en_cours','realisee','cloturee','annulee')),
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Seule la Direction générale émet, modifie, clôture ou annule une directive.
CREATE FUNCTION enforce_directive_rules() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' AND NOT is_active_director(NEW.issued_by) THEN
    RAISE EXCEPTION 'Seule la Direction générale émet des directives';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM projects WHERE id = NEW.project_id AND company_id = NEW.company_id) THEN
    RAISE EXCEPTION 'Directive : le projet n''appartient pas à cette filiale';
  END IF;
  IF TG_OP = 'UPDATE' THEN
    IF NEW.title <> OLD.title OR NEW.instructions <> OLD.instructions OR NEW.project_id <> OLD.project_id
       OR NEW.company_id <> OLD.company_id OR NEW.issued_by <> OLD.issued_by THEN
      RAISE EXCEPTION 'Le contenu d''une directive émise ne se modifie pas : l''annuler et en émettre une nouvelle';
    END IF;
    IF NEW.status IN ('cloturee','annulee') AND NEW.status <> OLD.status AND NOT is_active_director(NEW.closed_by) THEN
      RAISE EXCEPTION 'Seule la Direction générale clôture ou annule une directive';
    END IF;
    IF OLD.status IN ('cloturee','annulee') AND NEW.status <> OLD.status AND NOT is_active_director(NEW.closed_by) THEN
      RAISE EXCEPTION 'Seule la Direction générale rouvre une directive';
    END IF;
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER directives_rules BEFORE INSERT OR UPDATE ON directives FOR EACH ROW EXECUTE FUNCTION enforce_directive_rules();

GRANT SELECT, INSERT, UPDATE ON directives TO ilk_app;
GRANT SELECT, INSERT ON directive_updates TO ilk_app;
GRANT USAGE, SELECT ON directives_id_seq, directive_updates_id_seq TO ilk_app;
