
-- ============================================================================
-- MediCore Hospital CRM Database
-- Generated: 2026-04-05 23:08:52
-- Tables: 12 | Target: ~200,000 appointments
-- ============================================================================

DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS billing_invoices CASCADE;
DROP TABLE IF EXISTS prescriptions CASCADE;
DROP TABLE IF EXISTS lab_orders CASCADE;
DROP TABLE IF EXISTS diagnoses CASCADE;
DROP TABLE IF EXISTS admissions CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS staff CASCADE;
DROP TABLE IF EXISTS doctors CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS specialties CASCADE;
DROP TABLE IF EXISTS departments CASCADE;

-- ─── Reference Tables ───────────────────────────────────────────────────────

CREATE TABLE departments (
    department_id   SERIAL PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    location        VARCHAR(200),
    phone           VARCHAR(20),
    head_of_department VARCHAR(100)
);

CREATE TABLE specialties (
    specialty_id    SERIAL PRIMARY KEY,
    specialty_name  VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT
);

-- ─── People Tables ──────────────────────────────────────────────────────────

CREATE TABLE doctors (
    doctor_id       SERIAL PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    email           VARCHAR(100) UNIQUE,
    phone           VARCHAR(20),
    specialty_id    INTEGER NOT NULL REFERENCES specialties(specialty_id),
    department_id   INTEGER NOT NULL REFERENCES departments(department_id),
    hire_date       DATE NOT NULL,
    license_number  VARCHAR(20) UNIQUE,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE staff (
    staff_id        SERIAL PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    role            VARCHAR(50) NOT NULL,
    department_id   INTEGER NOT NULL REFERENCES departments(department_id),
    email           VARCHAR(100),
    phone           VARCHAR(20),
    hire_date       DATE NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE patients (
    patient_id      SERIAL PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    date_of_birth   DATE NOT NULL,
    gender          VARCHAR(10) NOT NULL,
    email           VARCHAR(100),
    phone           VARCHAR(20),
    address         VARCHAR(200),
    city            VARCHAR(50),
    blood_type      VARCHAR(5),
    emergency_contact_name  VARCHAR(100),
    emergency_contact_phone VARCHAR(20),
    registered_date DATE NOT NULL
);

-- ─── Operational Tables ─────────────────────────────────────────────────────

CREATE TABLE appointments (
    appointment_id  SERIAL PRIMARY KEY,
    patient_id      INTEGER NOT NULL REFERENCES patients(patient_id),
    doctor_id       INTEGER NOT NULL REFERENCES doctors(doctor_id),
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'Scheduled',
    reason          VARCHAR(200),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE admissions (
    admission_id    SERIAL PRIMARY KEY,
    patient_id      INTEGER NOT NULL REFERENCES patients(patient_id),
    doctor_id       INTEGER NOT NULL REFERENCES doctors(doctor_id),
    department_id   INTEGER NOT NULL REFERENCES departments(department_id),
    admission_date  DATE NOT NULL,
    discharge_date  DATE,
    room_number     VARCHAR(10),
    bed_number      VARCHAR(5),
    admission_type  VARCHAR(20) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'Active'
);

-- ─── Clinical Tables ────────────────────────────────────────────────────────

CREATE TABLE diagnoses (
    diagnosis_id    SERIAL PRIMARY KEY,
    admission_id    INTEGER NOT NULL REFERENCES admissions(admission_id),
    patient_id      INTEGER NOT NULL REFERENCES patients(patient_id),
    doctor_id       INTEGER NOT NULL REFERENCES doctors(doctor_id),
    diagnosis_code  VARCHAR(20) NOT NULL,
    diagnosis_description VARCHAR(200) NOT NULL,
    diagnosis_date  DATE NOT NULL,
    severity        VARCHAR(20) NOT NULL
);

CREATE TABLE lab_orders (
    lab_order_id    SERIAL PRIMARY KEY,
    appointment_id  INTEGER NOT NULL REFERENCES appointments(appointment_id),
    patient_id      INTEGER NOT NULL REFERENCES patients(patient_id),
    doctor_id       INTEGER NOT NULL REFERENCES doctors(doctor_id),
    test_name       VARCHAR(100) NOT NULL,
    test_category   VARCHAR(50) NOT NULL,
    order_date      DATE NOT NULL,
    result_date     DATE,
    result_value    VARCHAR(100),
    result_status   VARCHAR(20),
    notes           TEXT
);

CREATE TABLE prescriptions (
    prescription_id SERIAL PRIMARY KEY,
    appointment_id  INTEGER NOT NULL REFERENCES appointments(appointment_id),
    patient_id      INTEGER NOT NULL REFERENCES patients(patient_id),
    doctor_id       INTEGER NOT NULL REFERENCES doctors(doctor_id),
    medication_name VARCHAR(100) NOT NULL,
    dosage          VARCHAR(50) NOT NULL,
    frequency       VARCHAR(100) NOT NULL,
    duration_days   INTEGER NOT NULL,
    prescribed_date DATE NOT NULL,
    notes           TEXT
);

-- ─── Financial Tables ───────────────────────────────────────────────────────

CREATE TABLE billing_invoices (
    invoice_id      SERIAL PRIMARY KEY,
    patient_id      INTEGER NOT NULL REFERENCES patients(patient_id),
    admission_id    INTEGER REFERENCES admissions(admission_id),
    invoice_date    DATE NOT NULL,
    total_amount    DECIMAL(12,2) NOT NULL,
    discount        DECIMAL(12,2) DEFAULT 0.00,
    tax             DECIMAL(12,2) DEFAULT 0.00,
    net_amount      DECIMAL(12,2) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'Pending',
    due_date        DATE NOT NULL
);

CREATE TABLE payments (
    payment_id      SERIAL PRIMARY KEY,
    invoice_id      INTEGER NOT NULL REFERENCES billing_invoices(invoice_id),
    patient_id      INTEGER NOT NULL REFERENCES patients(patient_id),
    payment_date    DATE NOT NULL,
    amount          DECIMAL(12,2) NOT NULL,
    payment_method  VARCHAR(30) NOT NULL,
    transaction_reference VARCHAR(50),
    status          VARCHAR(20) NOT NULL DEFAULT 'Completed'
);

-- ─── Indexes ────────────────────────────────────────────────────────────────

CREATE INDEX idx_doctors_specialty ON doctors(specialty_id);
CREATE INDEX idx_doctors_department ON doctors(department_id);
CREATE INDEX idx_staff_department ON staff(department_id);
CREATE INDEX idx_patients_city ON patients(city);
CREATE INDEX idx_patients_blood_type ON patients(blood_type);
CREATE INDEX idx_patients_registered ON patients(registered_date);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_doctor ON appointments(doctor_id);
CREATE INDEX idx_appointments_date ON appointments(appointment_date);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE INDEX idx_admissions_patient ON admissions(patient_id);
CREATE INDEX idx_admissions_doctor ON admissions(doctor_id);
CREATE INDEX idx_admissions_department ON admissions(department_id);
CREATE INDEX idx_admissions_date ON admissions(admission_date);
CREATE INDEX idx_diagnoses_admission ON diagnoses(admission_id);
CREATE INDEX idx_diagnoses_patient ON diagnoses(patient_id);
CREATE INDEX idx_diagnoses_code ON diagnoses(diagnosis_code);
CREATE INDEX idx_lab_orders_appointment ON lab_orders(appointment_id);
CREATE INDEX idx_lab_orders_patient ON lab_orders(patient_id);
CREATE INDEX idx_prescriptions_appointment ON prescriptions(appointment_id);
CREATE INDEX idx_prescriptions_patient ON prescriptions(patient_id);
CREATE INDEX idx_billing_patient ON billing_invoices(patient_id);
CREATE INDEX idx_billing_admission ON billing_invoices(admission_id);
CREATE INDEX idx_billing_status ON billing_invoices(status);
CREATE INDEX idx_payments_invoice ON payments(invoice_id);
CREATE INDEX idx_payments_patient ON payments(patient_id);
CREATE INDEX idx_payments_method ON payments(payment_method);

