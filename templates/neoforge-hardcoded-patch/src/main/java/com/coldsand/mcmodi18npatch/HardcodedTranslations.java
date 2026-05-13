package com.coldsand.mcmodi18npatch;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import net.neoforged.fml.loading.FMLPaths;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class HardcodedTranslations {
    private static final Logger LOGGER = LoggerFactory.getLogger(HardcodedTranslations.class);
    private static final Gson GSON = new Gson();
    private final Map<String, String> translations;

    private HardcodedTranslations(Map<String, String> translations) {
        this.translations = Map.copyOf(translations);
    }

    public static HardcodedTranslations load() {
        Path path = FMLPaths.CONFIGDIR.get()
            .resolve("mc-mod-i18n")
            .resolve("hardcoded-map.json");
        if (!Files.isRegularFile(path)) {
            LOGGER.info("No mc-mod-i18n hardcoded map found at {}", path);
            return new HardcodedTranslations(Map.of());
        }

        try (Reader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            JsonObject root = JsonParser.parseReader(reader).getAsJsonObject();
            Map<String, String> loaded = new HashMap<>();
            for (Map.Entry<String, JsonElement> entry : root.entrySet()) {
                String translation = translationValue(entry.getValue());
                if (translation != null && !translation.isBlank()) {
                    loaded.put(entry.getKey(), translation);
                }
            }
            LOGGER.info("Loaded {} mc-mod-i18n hardcoded translations from {}", loaded.size(), path);
            return new HardcodedTranslations(loaded);
        } catch (IOException | IllegalStateException ex) {
            LOGGER.warn("Could not load mc-mod-i18n hardcoded map from {}", path, ex);
            return new HardcodedTranslations(Map.of());
        }
    }

    private static String translationValue(JsonElement value) {
        if (value == null || value.isJsonNull()) {
            return null;
        }
        if (value.isJsonPrimitive() && value.getAsJsonPrimitive().isString()) {
            return value.getAsString();
        }
        if (value.isJsonObject()) {
            JsonObject object = value.getAsJsonObject();
            JsonElement translation = object.get("translation");
            if (translation != null && translation.isJsonPrimitive() && translation.getAsJsonPrimitive().isString()) {
                return translation.getAsString();
            }
        }
        return null;
    }

    public String translate(String source) {
        return translations.get(source);
    }
}
