-- Décision de la Direction : la gestion financière de chaque filiale est séparée.
-- eurl medater et cabinet ILK ont chacun leur propre service financier ; il n'y a plus de service
-- financier commun ni de consolidation. Les autres services communs ne donnent plus accès aux finances.

-- Service financier propre au cabinet ILK (eurl medater a déjà CONST-FIN « Finances et contrats »).
INSERT INTO org_units (code, parent_code, company_code, name, kind, floor, modules, sort) VALUES
 ('ARCH-FIN', 'ARCH', 'ARCH', 'Comptabilité et finances du cabinet', 'department', 2, '{finance,crm,contracts}', 43);

-- Le service commun « Comptabilité et finances » est retiré (aucune autorisation ne peut plus le viser).
UPDATE org_units SET active = false, modules = '{}' WHERE code = 'SHARED-FIN';

-- La Direction générale du groupe n'ouvre plus les finances par département : le Directeur général
-- garde l'accès à chaque filiale, séparément.
UPDATE org_units SET modules = array_remove(modules, 'finance') WHERE code = 'SHARED-EXEC';

-- Les autorisations existantes sur le service commun supprimé sont révoquées (traçabilité conservée).
UPDATE grants SET status = 'revoked', revoked_at = now(), changed_by = granted_by
 WHERE scope_type = 'org_unit' AND scope_ref = 'SHARED-FIN' AND status <> 'revoked'
   AND EXISTS (SELECT 1 FROM users WHERE id = grants.granted_by AND is_group_director AND enabled);

-- Une écriture financière ne peut référencer qu'un tiers, un projet et un marché de sa propre filiale
-- (défense en base, en plus du contrôle de l'API).
CREATE FUNCTION enforce_same_company_finance() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'invoices' THEN
    IF EXISTS (SELECT 1 FROM parties WHERE id = NEW.party_id AND company_id <> NEW.company_id)
       OR (NEW.project_id IS NOT NULL AND EXISTS (SELECT 1 FROM projects WHERE id = NEW.project_id AND company_id <> NEW.company_id))
       OR (NEW.contract_id IS NOT NULL AND EXISTS (SELECT 1 FROM contracts WHERE id = NEW.contract_id AND company_id <> NEW.company_id)) THEN
      RAISE EXCEPTION 'Facture : toutes les références doivent appartenir à la même filiale';
    END IF;
  ELSIF TG_TABLE_NAME = 'payments' THEN
    IF EXISTS (SELECT 1 FROM invoices WHERE id = NEW.invoice_id AND company_id <> NEW.company_id) THEN
      RAISE EXCEPTION 'Paiement : la facture appartient à une autre filiale';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER invoices_same_company BEFORE INSERT OR UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION enforce_same_company_finance();
CREATE TRIGGER payments_same_company BEFORE INSERT OR UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION enforce_same_company_finance();
