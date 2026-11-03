-- ==============================================================================
-- Azure Student Fee Management System - Database Schema
-- Compatible with SQL Server 2022 & Azure SQL Database
-- ==============================================================================

-- Create Database if not running inside Azure SQL (where DB is pre-provisioned)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'StudentFeeManagementDB')
BEGIN
    CREATE DATABASE [StudentFeeManagementDB];
END
GO

USE [StudentFeeManagementDB];
GO

-- ------------------------------------------------------------------------------
-- 1. Courses Table
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.Courses', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Courses (
        course_id INT IDENTITY(1,1) PRIMARY KEY,
        course_code VARCHAR(30) NOT NULL CONSTRAINT UQ_Courses_Code UNIQUE,
        course_name NVARCHAR(200) NOT NULL,
        department NVARCHAR(100) NOT NULL,
        duration_semesters INT NOT NULL DEFAULT 8,
        base_fee_per_semester DECIMAL(12,2) NOT NULL CHECK (base_fee_per_semester >= 0),
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_Courses_CreatedAt DEFAULT SYSUTCDATETIME()
    );
END
GO

-- ------------------------------------------------------------------------------
-- 2. Academic Terms Table
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.AcademicTerms', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.AcademicTerms (
        term_id INT IDENTITY(1,1) PRIMARY KEY,
        term_code VARCHAR(30) NOT NULL CONSTRAINT UQ_Terms_Code UNIQUE,
        term_name NVARCHAR(100) NOT NULL,
        academic_year VARCHAR(20) NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_Terms_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_AcademicTerms_Dates CHECK (end_date >= start_date)
    );
END
GO

-- ------------------------------------------------------------------------------
-- 3. Fee Categories Table (Tuition, Laboratory, Library, Accommodation, etc.)
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.FeeCategories', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.FeeCategories (
        category_id INT IDENTITY(1,1) PRIMARY KEY,
        category_name NVARCHAR(100) NOT NULL CONSTRAINT UQ_FeeCategories_Name UNIQUE,
        description NVARCHAR(255) NULL,
        is_mandatory BIT NOT NULL DEFAULT 1,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_FeeCategories_CreatedAt DEFAULT SYSUTCDATETIME()
    );
END
GO

-- ------------------------------------------------------------------------------
-- 4. Students Table
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.Students', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Students (
        student_id INT IDENTITY(1,1) PRIMARY KEY,
        student_code VARCHAR(50) NOT NULL CONSTRAINT UQ_Students_Code UNIQUE,
        first_name NVARCHAR(100) NOT NULL,
        last_name NVARCHAR(100) NOT NULL,
        email VARCHAR(255) NOT NULL CONSTRAINT UQ_Students_Email UNIQUE,
        phone VARCHAR(30) NULL,
        course_id INT NOT NULL,
        current_semester INT NOT NULL DEFAULT 1,
        enrollment_date DATE NOT NULL DEFAULT CAST(GETUTCDATE() AS DATE),
        status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' 
            CONSTRAINT CK_Students_Status CHECK (status IN ('ACTIVE', 'GRADUATED', 'SUSPENDED', 'WITHDRAWN')),
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_Students_CreatedAt DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_Students_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Students_Courses FOREIGN KEY (course_id) REFERENCES dbo.Courses(course_id)
    );
END
GO

-- ------------------------------------------------------------------------------
-- 5. Invoices Table
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.Invoices', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Invoices (
        invoice_id INT IDENTITY(1,1) PRIMARY KEY,
        invoice_number VARCHAR(60) NOT NULL CONSTRAINT UQ_Invoices_Number UNIQUE,
        student_id INT NOT NULL,
        term_id INT NOT NULL,
        total_amount DECIMAL(12,2) NOT NULL CHECK (total_amount >= 0),
        paid_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 CHECK (paid_amount >= 0),
        due_amount AS (total_amount - paid_amount) PERSISTED,
        due_date DATE NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
            CONSTRAINT CK_Invoices_Status CHECK (status IN ('PENDING', 'PARTIAL', 'PAID', 'OVERDUE', 'CANCELLED')),
        notes NVARCHAR(500) NULL,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_Invoices_CreatedAt DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_Invoices_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Invoices_Students FOREIGN KEY (student_id) REFERENCES dbo.Students(student_id),
        CONSTRAINT FK_Invoices_AcademicTerms FOREIGN KEY (term_id) REFERENCES dbo.AcademicTerms(term_id)
    );
END
GO

-- ------------------------------------------------------------------------------
-- 6. Invoice Line Items Table
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.InvoiceItems', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.InvoiceItems (
        item_id INT IDENTITY(1,1) PRIMARY KEY,
        invoice_id INT NOT NULL,
        category_id INT NOT NULL,
        description NVARCHAR(255) NOT NULL,
        amount DECIMAL(12,2) NOT NULL CHECK (amount >= 0),
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_InvoiceItems_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_InvoiceItems_Invoices FOREIGN KEY (invoice_id) REFERENCES dbo.Invoices(invoice_id) ON DELETE CASCADE,
        CONSTRAINT FK_InvoiceItems_FeeCategories FOREIGN KEY (category_id) REFERENCES dbo.FeeCategories(category_id)
    );
END
GO

-- ------------------------------------------------------------------------------
-- 7. Payments / Transactions Table
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.Payments', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Payments (
        payment_id INT IDENTITY(1,1) PRIMARY KEY,
        transaction_reference VARCHAR(100) NOT NULL CONSTRAINT UQ_Payments_Ref UNIQUE,
        invoice_id INT NOT NULL,
        amount_paid DECIMAL(12,2) NOT NULL CHECK (amount_paid > 0),
        payment_method VARCHAR(50) NOT NULL 
            CONSTRAINT CK_Payments_Method CHECK (payment_method IN ('CREDIT_CARD', 'DEBIT_CARD', 'BANK_TRANSFER', 'UPI', 'ONLINE_PORTAL', 'CASH', 'CHEQUE')),
        payment_status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS'
            CONSTRAINT CK_Payments_Status CHECK (payment_status IN ('SUCCESS', 'PENDING', 'FAILED', 'REFUNDED')),
        gateway_response NVARCHAR(MAX) NULL,
        payment_date DATETIME2(3) NOT NULL CONSTRAINT DF_Payments_Date DEFAULT SYSUTCDATETIME(),
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_Payments_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Payments_Invoices FOREIGN KEY (invoice_id) REFERENCES dbo.Invoices(invoice_id)
    );
END
GO

-- ------------------------------------------------------------------------------
-- 8. Reminders Log Table (Used by scripts, functions & Logic App)
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.RemindersLog', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.RemindersLog (
        reminder_id INT IDENTITY(1,1) PRIMARY KEY,
        invoice_id INT NOT NULL,
        student_id INT NOT NULL,
        recipient_email VARCHAR(255) NOT NULL,
        reminder_type VARCHAR(50) NOT NULL 
            CONSTRAINT CK_Reminders_Type CHECK (reminder_type IN ('UPCOMING_DUE', 'DUE_TODAY', 'OVERDUE_FIRST', 'OVERDUE_FINAL', 'CUSTOM')),
        channel VARCHAR(20) NOT NULL DEFAULT 'EMAIL'
            CONSTRAINT CK_Reminders_Channel CHECK (channel IN ('EMAIL', 'SMS', 'TEAMS', 'PORTAL')),
        delivery_status VARCHAR(20) NOT NULL DEFAULT 'SENT'
            CONSTRAINT CK_Reminders_DeliveryStatus CHECK (delivery_status IN ('PENDING', 'SENT', 'FAILED', 'SKIPPED')),
        error_details NVARCHAR(MAX) NULL,
        sent_at DATETIME2(3) NOT NULL CONSTRAINT DF_Reminders_SentAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_RemindersLog_Invoices FOREIGN KEY (invoice_id) REFERENCES dbo.Invoices(invoice_id),
        CONSTRAINT FK_RemindersLog_Students FOREIGN KEY (student_id) REFERENCES dbo.Students(student_id)
    );
END
GO

-- ------------------------------------------------------------------------------
-- 9. Audit Log Table
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.AuditLogs', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.AuditLogs (
        log_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        entity_name VARCHAR(60) NOT NULL,
        entity_id INT NOT NULL,
        action VARCHAR(40) NOT NULL, -- INSERT, UPDATE, PAYMENT_APPLIED, STATUS_CHANGE
        performed_by VARCHAR(100) NOT NULL DEFAULT 'SYSTEM',
        performed_at DATETIME2(3) NOT NULL CONSTRAINT DF_AuditLogs_PerformedAt DEFAULT SYSUTCDATETIME(),
        old_values NVARCHAR(MAX) NULL,
        new_values NVARCHAR(MAX) NULL
    );
END
GO

-- ------------------------------------------------------------------------------
-- Performance Indexes
-- ------------------------------------------------------------------------------
CREATE NONCLUSTERED INDEX IX_Students_CourseId ON dbo.Students(course_id);
CREATE NONCLUSTERED INDEX IX_Students_Status ON dbo.Students(status);
CREATE NONCLUSTERED INDEX IX_Invoices_StudentId ON dbo.Invoices(student_id);
CREATE NONCLUSTERED INDEX IX_Invoices_Status_DueDate ON dbo.Invoices(status, due_date) INCLUDE (total_amount, paid_amount);
CREATE NONCLUSTERED INDEX IX_Payments_InvoiceId ON dbo.Payments(invoice_id);
CREATE NONCLUSTERED INDEX IX_RemindersLog_InvoiceId_SentAt ON dbo.RemindersLog(invoice_id, sent_at);
GO

-- ------------------------------------------------------------------------------
-- Trigger to Automatically Update Invoices Status When Payments Are Inserted
-- ------------------------------------------------------------------------------
CREATE OR ALTER TRIGGER trg_AfterPaymentInsert
ON dbo.Payments
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    -- Update paid_amount and status for affected invoices
    UPDATE inv
    SET inv.paid_amount = ISNULL(pay_agg.total_paid, 0),
        inv.status = CASE 
            WHEN ISNULL(pay_agg.total_paid, 0) >= inv.total_amount THEN 'PAID'
            WHEN ISNULL(pay_agg.total_paid, 0) > 0 AND ISNULL(pay_agg.total_paid, 0) < inv.total_amount THEN 'PARTIAL'
            WHEN inv.due_date < CAST(GETUTCDATE() AS DATE) THEN 'OVERDUE'
            ELSE 'PENDING'
        END,
        inv.updated_at = SYSUTCDATETIME()
    FROM dbo.Invoices inv
    INNER JOIN (
        SELECT DISTINCT invoice_id FROM inserted
    ) ins ON inv.invoice_id = ins.invoice_id
    CROSS APPLY (
        SELECT SUM(amount_paid) AS total_paid
        FROM dbo.Payments
        WHERE invoice_id = inv.invoice_id AND payment_status = 'SUCCESS'
    ) pay_agg;
END;
GO

