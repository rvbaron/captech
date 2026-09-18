-- Provider schema and stored procedures

CREATE TABLE providers (
    provider_id INT PRIMARY KEY,
    provider_name VARCHAR(255) NOT NULL,
    eligibility_status VARCHAR(50)
);

CREATE TABLE members (
    member_id INT PRIMARY KEY,
    provider_id INT,
    enrollment_date DATE,
    FOREIGN KEY (provider_id) REFERENCES providers(provider_id)
);

CREATE PROCEDURE validate_provider
    @provider_id INT
AS
BEGIN
    UPDATE providers
    SET eligibility_status = 'VALIDATED'
    WHERE provider_id = @provider_id;

    EXEC log_validation @provider_id;
END;

CREATE PROCEDURE log_validation
    @provider_id INT
AS
BEGIN
    INSERT INTO audit_log (provider_id, action, action_date)
    VALUES (@provider_id, 'VALIDATION', GETDATE());
END;
