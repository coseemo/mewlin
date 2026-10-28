MEWLIN POMODORO - cartella assets
Metti qui GIF (anche .webp/.apng animati) o .png con questi nomi. Se un file manca, l'app mostra un placeholder.
Le immagini vengono ingrandite solo di multipli interi (x2, x3...) per restare nitide: disegnale piccole!
Sfondo trasparente consigliato per tutto tranne scene_bg. Opzionale: font.ttf (font pixel per i testi).

nome (area massima in pixel finestra) - cosa deve mostrare
scene_bg  (400x300, es. 100x75 -> x4) - sfondo stanza: muro, pavimento, finestra, mensola
cat_idle  (320x205, es. 80x51 -> x4) - gatto stregone che dorme sul pavimento
cat_study  (380x245, es. 95x61 -> x4) - gatto che legge + pentolone con pozione, tutto in una GIF (es. 190x120)
cauldron  (165x155, es. 41x38 -> x4) - OPZIONALE: pentolone separato (non serve se e' gia' dentro cat_study)
cat_break  (170x130, es. 42x32 -> x4) - gatto che corre/insegue (il codice lo sposta e lo specchia)
bat  (56x40, es. 14x10 -> x4) - pipistrello (il codice ne fa volare 3)
plate  (400x116, es. 100x29 -> x4) - cornice del contatore (il testo lo scrive il codice)
button  (124x46, es. 31x11 -> x4) - sfondo dei bottoni cicli/reset/opzioni
panel  (400x112, es. 100x28 -> x4) - pannello del player musicale
icon_book  (28x28, es. 7x7 -> x4) - icona cicli
icon_reset  (28x28, es. 7x7 -> x4) - icona reset
icon_gear  (28x28, es. 7x7 -> x4) - icona opzioni
icon_play  (44x44, es. 11x11 -> x4) - tasto play
icon_pause  (44x44, es. 11x11 -> x4) - tasto pausa
icon_prev  (28x28, es. 7x7 -> x4) - canale precedente
icon_next  (28x28, es. 7x7 -> x4) - canale successivo
icon_skip  (28x28, es. 7x7 -> x4) - salta alla fine della fase (freccia verso destra)

EDITOR POSIZIONI: premi L nell'app. N = prossimo elemento, frecce = sposta (Shift = 5px), + / - = ingrandimento,
, / . = velocita' animazione, H = nascondi/mostra (es. cauldron se e' gia' dentro cat_study), R = azzera l'elemento, L = salva (assets/layout.json) ed esci.
In layout.json puoi anche cambiare "inset": [sx, alto, dx, basso] (frazioni) per i margini dei testi in plate/panel/button.
