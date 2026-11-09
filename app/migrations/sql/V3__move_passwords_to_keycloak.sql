-- Пароли и роли переносятся в Keycloak. Локальные bcrypt-хеши невозможно
-- превратить в учётные данные Keycloak, поэтому старые записи удаляются:
-- пользователи регистрируются заново уже через Keycloak.
TRUNCATE TABLE "user" RESTART IDENTITY;

ALTER TABLE "user" DROP COLUMN password;
ALTER TABLE "user" ADD COLUMN keycloak_id VARCHAR(36) NOT NULL;

CREATE UNIQUE INDEX idx_user_keycloak_id ON "user" (keycloak_id);
