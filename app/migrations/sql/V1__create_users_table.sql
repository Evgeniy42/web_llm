CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL
);

CREATE UNIQUE INDEX idx_user_username ON "user" (username);
CREATE UNIQUE INDEX idx_user_email ON "user" (email);
