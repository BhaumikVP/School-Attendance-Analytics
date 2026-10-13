

CREATE DATABASE IF NOT EXISTS attendance;
USE attendance;

CREATE TABLE classes (
    classID   INT AUTO_INCREMENT PRIMARY KEY,
    className VARCHAR(10) NOT NULL,
    division  VARCHAR(5)  NOT NULL,
    UNIQUE KEY uq_class (className, division)
);

CREATE TABLE teachers (
    teacherID        INT AUTO_INCREMENT PRIMARY KEY,
    t_name           VARCHAR(100) NOT NULL,
    email            VARCHAR(150) NOT NULL UNIQUE,
    passwordHash     VARCHAR(255) NOT NULL,
    t_role           ENUM('Teacher', 'Administrator') NOT NULL DEFAULT 'Teacher',
    assigned_classID INT NULL,
    FOREIGN KEY (assigned_classID) REFERENCES classes(classID) ON DELETE SET NULL
);

CREATE TABLE students (
    studentID   INT AUTO_INCREMENT PRIMARY KEY,
    s_name      VARCHAR(100) NOT NULL,
    classID     INT NOT NULL,
    rollNo      VARCHAR(10) NOT NULL,
    gender      ENUM('Male', 'Female') NOT NULL,
    dob         DATE NOT NULL,
    parentName  VARCHAR(100),
    parentPhone VARCHAR(20),
    UNIQUE KEY uq_roll (classID, rollNo),
    FOREIGN KEY (classID) REFERENCES classes(classID)
);

CREATE TABLE attendance (
    attendanceID INT AUTO_INCREMENT PRIMARY KEY,
    studentID    INT NOT NULL,
    date_        DATE NOT NULL,
    stat         ENUM('Present', 'Absent', 'Late', 'Medical Leave') NOT NULL,
    remarks      VARCHAR(255),
    markedBy     INT,
    UNIQUE KEY uq_attendance (studentID, date_),
    FOREIGN KEY (studentID) REFERENCES students(studentID) ON DELETE CASCADE,
    FOREIGN KEY (markedBy) REFERENCES teachers(teacherID)
);

CREATE TABLE riskScores (
    riskID          INT AUTO_INCREMENT PRIMARY KEY,
    studentID       INT NOT NULL,
    calculatedDate  DATE NOT NULL,
    attendancepct   DECIMAL(5,2),
    consecutive     INT,
    riskProbability DECIMAL(5,4),
    riskLevel       ENUM('Low', 'Medium', 'High'),
    UNIQUE KEY uq_risk (studentID, calculatedDate),
    FOREIGN KEY (studentID) REFERENCES students(studentID) ON DELETE CASCADE
);
