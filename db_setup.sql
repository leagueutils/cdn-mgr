CREATE schema cdn;
CREATE schema gfx;

CREATE TABLE cdn.media (
    media_id UUID PRIMARY KEY,
    media_class VARCHAR(16),
    hash VARCHAR(1024) UNIQUE
);

CREATE TABLE cdn.links (
    media_id UUID REFERENCES cdn.media(media_id) ON DELETE CASCADE,
    link VARCHAR(128) NOT NULL,
    ttl TIMESTAMP
);

CREATE TABLE gfx.templates(
    template_id UUID REFERENCES cdn.media(media_id) ON DELETE CASCADE,
    template_type VARCHAR(16),
    tournament_id INTEGER,
    UNIQUE(template_type, tournament_id)
);

CREATE TABLE gfx.template_components(
    template_id UUID REFERENCES gfx.templates(template_id) ON DELETE CASCADE,
    component_type VARCHAR(8),
    component_value JSONB
);

CREATE TABLE gfx.fonts(
    font_path VARCHAR(128) REFERENCES cdn.links(link) ON DELETE CASCADE,
    tournament_id INTEGER PRIMARY KEY
);
