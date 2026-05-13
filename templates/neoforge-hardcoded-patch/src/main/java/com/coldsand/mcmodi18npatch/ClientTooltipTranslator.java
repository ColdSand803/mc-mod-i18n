package com.coldsand.mcmodi18npatch;

import java.util.List;
import net.minecraft.network.chat.Component;
import net.neoforged.neoforge.event.entity.player.ItemTooltipEvent;

public final class ClientTooltipTranslator {
    private final HardcodedTranslations translations;

    public ClientTooltipTranslator(HardcodedTranslations translations) {
        this.translations = translations;
    }

    public void onTooltip(ItemTooltipEvent event) {
        List<Component> lines = event.getToolTip();
        for (int index = 0; index < lines.size(); index += 1) {
            Component line = lines.get(index);
            String replacement = translations.translate(line.getString());
            if (replacement != null) {
                lines.set(index, Component.literal(replacement).withStyle(line.getStyle()));
            }
        }
    }
}
