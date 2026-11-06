"""Versioned schema migrations. Append new steps - never edit old ones."""

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE provider_config (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        provider_name TEXT NOT NULL,
        base_url TEXT NOT NULL,
        model TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE preferences (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        theme TEXT NOT NULL DEFAULT 'dark',
        active_course TEXT NOT NULL DEFAULT 'python',
        default_tutor_mode TEXT NOT NULL DEFAULT 'learn',
        editor_font_size INTEGER NOT NULL DEFAULT 14,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL DEFAULT 'New chat',
        mode TEXT NOT NULL DEFAULT 'learn',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX idx_conversations_user ON conversations(user_id, updated_at DESC);

    CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('user','assistant')),
        content TEXT NOT NULL,
        mode TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX idx_messages_conversation ON messages(conversation_id, id);

    CREATE TABLE courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        language TEXT NOT NULL,
        level TEXT NOT NULL DEFAULT 'beginner',
        status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('complete','planned')),
        overview TEXT NOT NULL DEFAULT '',
        prerequisites TEXT NOT NULL DEFAULT '[]',
        outline TEXT NOT NULL DEFAULT '[]',
        order_index INTEGER NOT NULL DEFAULT 0,
        content_version TEXT NOT NULL DEFAULT '1'
    );

    CREATE TABLE lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        slug TEXT NOT NULL,
        title TEXT NOT NULL,
        order_index INTEGER NOT NULL DEFAULT 0,
        summary TEXT NOT NULL DEFAULT '',
        objectives TEXT NOT NULL DEFAULT '[]',
        sections TEXT NOT NULL DEFAULT '[]',
        example TEXT NOT NULL DEFAULT '{}',
        quiz TEXT NOT NULL DEFAULT '[]',
        UNIQUE (course_id, slug)
    );
    CREATE INDEX idx_lessons_course ON lessons(course_id, order_index);

    CREATE TABLE exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
        lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
        kind TEXT NOT NULL CHECK (kind IN
            ('mcq','predict_output','fill_blank','find_bug','write_program')),
        title TEXT NOT NULL,
        prompt TEXT NOT NULL,
        difficulty INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),
        language TEXT NOT NULL DEFAULT 'python',
        starter_code TEXT NOT NULL DEFAULT '',
        test_spec TEXT,
        answer TEXT,
        hints TEXT NOT NULL DEFAULT '[]',
        solution TEXT NOT NULL DEFAULT '{}',
        order_index INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX idx_exercises_course ON exercises(course_id, order_index);
    CREATE INDEX idx_exercises_lesson ON exercises(lesson_id, order_index);

    CREATE TABLE lesson_completions (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
        time_spent_seconds INTEGER NOT NULL DEFAULT 0,
        completed_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, lesson_id)
    );

    CREATE TABLE quiz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
        score INTEGER NOT NULL,
        total INTEGER NOT NULL,
        details TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX idx_quiz_results_user ON quiz_results(user_id, lesson_id);

    CREATE TABLE exercise_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
        submission TEXT NOT NULL DEFAULT '{}',
        passed INTEGER NOT NULL DEFAULT 0,
        hints_used INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX idx_attempts_user_ex ON exercise_attempts(user_id, exercise_id, created_at);

    CREATE TABLE projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        difficulty INTEGER NOT NULL DEFAULT 1,
        language TEXT NOT NULL DEFAULT 'python',
        skills TEXT NOT NULL DEFAULT '[]',
        requirements TEXT NOT NULL DEFAULT '[]',
        milestones TEXT NOT NULL DEFAULT '[]',
        starter_code TEXT NOT NULL DEFAULT '',
        testing_instructions TEXT NOT NULL DEFAULT '',
        challenges TEXT NOT NULL DEFAULT '[]',
        order_index INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE project_progress (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        milestone_index INTEGER NOT NULL,
        completed_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, project_id, milestone_index)
    );

    CREATE TABLE activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        ref TEXT NOT NULL DEFAULT '',
        detail TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX idx_activity_user ON activity_log(user_id, created_at DESC);

    CREATE TABLE app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """),
    (2, """
    CREATE TABLE hint_reveals (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
        revealed INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, exercise_id)
    );
    """),
    (3, """
    ALTER TABLE exercises ADD COLUMN options TEXT;
    """),
]
