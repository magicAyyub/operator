#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <ctype.h>

#define BUFFER_SIZE 4096
#define MAX_LINE_LENGTH 2048
#define MAX_COLUMNS 100

// Structure pour stocker les colonnes du header et leur position
typedef struct {
    char *names[MAX_COLUMNS];  // Noms des colonnes du header
    int count;                 // Nombre de colonnes réelles
} HeaderInfo;

typedef struct {
    char *values[MAX_COLUMNS];
    int count;
} DataLine;

HeaderInfo header_info = {0};  // Variable globale pour stocker l'information du header

void free_data_line(DataLine *line) {
    for (int i = 0; i < line->count; i++) {
        free(line->values[i]);
    }
    line->count = 0;
}

void free_header_info() {
    for (int i = 0; i < header_info.count; i++) {
        free(header_info.names[i]);
    }
    header_info.count = 0;
}

bool should_ignore_line(const char *line) {
    bool only_separators = true;
    bool has_content = false;
    
    while (*line) {
        if (*line == '-' || *line == '+' || *line == '|' || isspace(*line)) {
            line++;
            continue;
        }
        only_separators = false;
        has_content = true;
        break;
    }
    
    return only_separators || !has_content;
}

void trim(char *str) {
    char *start = str;
    char *end;
    
    while (isspace((unsigned char)*start)) start++;
    
    if (*start == 0) {
        str[0] = 0;
        return;
    }
    
    end = start + strlen(start) - 1;
    while (end > start && isspace((unsigned char)*end)) end--;
    end[1] = 0;
    
    if (start != str) {
        memmove(str, start, strlen(start) + 1);
    }
}

bool has_meaningful_content(const char *value) {
    if (strcmp(value, "...") == 0) return false;
    
    while (*value) {
        if (!isspace((unsigned char)*value) && *value != '-' && *value != '|' && 
            *value != '+' && *value != '.') {
            return true;
        }
        value++;
    }
    return false;
}

// Fonction améliorée pour traiter le header
bool process_header(char *header_line) {
    char *token;
    char *saveptr;
    header_info.count = 0;
    
    // Premier token
    token = strtok_r(header_line, "|", &saveptr);
    
    // Parcourir tous les tokens
    while (token != NULL && header_info.count < MAX_COLUMNS) {
        char *value = strdup(token);
        trim(value);
        
        // Ne garder que les noms de colonnes non vides
        if (strlen(value) > 0 && has_meaningful_content(value)) {
            header_info.names[header_info.count++] = value;
        } else {
            free(value);
        }
        
        token = strtok_r(NULL, "|", &saveptr);
    }
    
    return header_info.count > 0;
}

bool parse_line(char *line, DataLine *data_line, bool is_header) {
    if (should_ignore_line(line)) {
        return false;
    }

    char *token;
    char *saveptr;
    data_line->count = 0;
    bool has_any_content = false;
    
    // Traitement spécial pour le header
    if (is_header) {
        return process_header(line);
    }
    
    // Pour les lignes de données
    token = strtok_r(line, "|", &saveptr);
    while (data_line->count < header_info.count) {
        if (token != NULL) {
            char *value = strdup(token);
            trim(value);
            
            if (has_meaningful_content(value)) {
                has_any_content = true;
            }
            
            data_line->values[data_line->count++] = value;
            token = strtok_r(NULL, "|", &saveptr);
        } else {
            data_line->values[data_line->count++] = strdup("");
        }
    }
    
    if (!has_any_content) {
        free_data_line(data_line);
        return false;
    }
    
    return true;
}

void write_csv_field(FILE *output, const char *value, bool is_last) {
    // Vérifier si la valeur nécessite des guillemets
    bool needs_quotes = strchr(value, ',') != NULL || strchr(value, '"') != NULL;
    
    if (needs_quotes) {
        fprintf(output, "\"");
        // Échapper les guillemets dans la valeur
        for (const char *p = value; *p; p++) {
            if (*p == '"') {
                fprintf(output, "\"\"");
            } else {
                fputc(*p, output);
            }
        }
        fprintf(output, "\"");
    } else {
        fprintf(output, "%s", value);
    }
    
    if (!is_last) {
        fprintf(output, ",");
    }
}

bool process_file(const char *input_path, const char *output_path) {
    FILE *input = fopen(input_path, "r");
    if (!input) {
        fprintf(stderr, "Erreur: Impossible d'ouvrir le fichier d'entree %s\n", input_path);
        return false;
    }
    
    FILE *output = fopen(output_path, "w");
    if (!output) {
        fprintf(stderr, "Erreur: Impossible d'ouvrir le fichier de sortie %s\n", output_path);
        fclose(input);
        return false;
    }
    
    char line[MAX_LINE_LENGTH];
    DataLine data_line = {0};
    int line_count = 0;
    bool header_processed = false;
    
    while (fgets(line, sizeof(line), input)) {
        line[strcspn(line, "\n")] = 0;
        
        if (!header_processed) {
            if (parse_line(line, &data_line, true)) {
                // Écrire le header
                for (int i = 0; i < header_info.count; i++) {
                    write_csv_field(output, header_info.names[i], i == header_info.count - 1);
                }
                fprintf(output, "\n");
                header_processed = true;
                line_count++;
            }
        } else if (parse_line(line, &data_line, false)) {
            // Écrire les données
            for (int i = 0; i < data_line.count; i++) {
                write_csv_field(output, data_line.values[i], i == data_line.count - 1);
            }
            fprintf(output, "\n");
            line_count++;
            free_data_line(&data_line);
        }
    }
    
    fclose(input);
    fclose(output);
    printf("Traitement termine: %d lignes ecrites dans %s\n", line_count, output_path);
    printf("Nombre de colonnes: %d\n", header_info.count);
    
    free_header_info();
    return true;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <fichier_entree> <fichier_sortie>\n", argv[0]);
        return 1;
    }
    
    if (!process_file(argv[1], argv[2])) {
        fprintf(stderr, "Erreur lors du traitement du fichier\n");
        return 1;
    }
    
    return 0;
}