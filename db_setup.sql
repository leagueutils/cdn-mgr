CREATE schema cdn;

CREATE TABLE cdn.media (
    media_id UUID PRIMARY KEY,
    media_class VARCHAR(16),
    hash VARCHAR(1024) UNIQUE
);

CREATE TABLE cdn.links (
    media_id UUID REFERENCES cdn.media(media_id),
    link VARCHAR(128) NOT NULL,
    ttl TIMESTAMP
);
