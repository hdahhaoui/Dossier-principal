import streamlit as st
import requests
import json
import re
import openai

# Configuration des clés API
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY")

# Titre de l'application
st.title("Simulation de consommation énergétique d'un climatiseur (7 jours)")

# Section 1: Caractéristiques du climatiseur
st.header("1. Données du climatiseur")

# Initialisation des variables de session
if 'ac_data_ok' not in st.session_state:
    st.session_state.ac_data_ok = False

# Champ de texte pour le modèle
modele = st.text_input("Modèle du climatiseur :", 
                      help="Ex: Daikin FTXF35C / LG S12EQ")

def extract_technical_data(response_text):
    """Extrait les données techniques de la réponse texte avec gestion robuste"""
    data = {'consommation': None, 'puissance': None, 'inverter': None}
    
    # Tentative d'extraction JSON
    try:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_data = json.loads(json_match.group())
            data['consommation'] = float(json_data.get('consommation_kW', 0))
            data['puissance'] = float(json_data.get('puissance_frigorifique_kW', 0))
            data['inverter'] = bool(json_data.get('inverter', False))
            return data
    except:
        pass
    
    # Fallback: Extraction par regex améliorée
    patterns = {
        'consommation': r'(consommation|puissance électrique)[^\d]*([\d,\.]+)\s*kW',
        'puissance': r'(puissance frigorifique|capacité de refroidissement)[^\d]*([\d,\.]+)\s*kW',
        'btu': r'(\d+)\s*BTU',
        'inverter': r'(inverter|technologie à vitesse variable)',
        'non_inverter': r'(non inverter|technologie fixe)'
    }
    
    # Extraction consommation
    match = re.search(patterns['consommation'], response_text, re.IGNORECASE)
    if match:
        try:
            data['consommation'] = float(match.group(2).replace(',', '.'))
        except:
            pass
    
    # Extraction puissance frigorifique
    match = re.search(patterns['puissance'], response_text, re.IGNORECASE)
    if match:
        try:
            data['puissance'] = float(match.group(2).replace(',', '.'))
        except:
            pass
    else:
        # Conversion BTU si nécessaire
        btu_match = re.search(patterns['btu'], response_text, re.IGNORECASE)
        if btu_match:
            try:
                btu = float(btu_match.group(1))
                data['puissance'] = round(btu * 0.00029307107, 2)
            except:
                pass
    
    # Détection technologie Inverter
    if re.search(patterns['inverter'], response_text, re.IGNORECASE):
        data['inverter'] = True
    elif re.search(patterns['non_inverter'], response_text, re.IGNORECASE):
        data['inverter'] = False
    
    return data

if st.button("Obtenir les données techniques via DeepSeek"):
    if DEEPSEEK_API_KEY:
        openai.api_base = "https://api.deepseek.com/v1"
        openai.api_key = DEEPSEEK_API_KEY
        
        prompt = f"""
        Pour le climatiseur {modele}, fournir STRICTEMENT les informations suivantes au format JSON:
        {{
            "consommation_kW": "float (puissance électrique en kilowatts)",
            "puissance_frigorifique_kW": "float (puissance de refroidissement en kilowatts)",
            "inverter": "boolean"
        }}
        Si une information est inconnue, utiliser null.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="deepseek-chat",
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.1,
                max_tokens=300
            )
            
            response_text = response.choices[0].message.content
            technical_data = extract_technical_data(response_text)
            
            # Enregistrement des données
            st.session_state.ac_modele = modele
            st.session_state.ac_conso = technical_data['consommation']
            st.session_state.ac_froid = technical_data['puissance']
            st.session_state.ac_inverter = technical_data['inverter']
            
            # Validation des données
            required_fields = [technical_data['consommation'], 
                             technical_data['puissance'], 
                             technical_data['inverter']]
            st.session_state.ac_data_ok = all(f is not None for f in required_fields)
            
            # Affichage debug
            with st.expander("Réponse brute de l'API"):
                st.code(response_text)
                
            if not st.session_state.ac_data_ok:
                st.warning("Certaines données n'ont pas pu être récupérées. Complétez manuellement.")
                
        except Exception as e:
            st.error(f"Erreur API: {str(e)}")
            st.session_state.ac_data_ok = False
    else:
        st.error("Clé API DeepSeek non configurée")

# Formulaire manuel
if not st.session_state.get('ac_data_ok', False):
    st.subheader("Saisie manuelle des données")
    
    col1, col2 = st.columns(2)
    with col1:
        conso = st.number_input("Consommation électrique (kW)", 
                              min_value=0.1, 
                              max_value=10.0, 
                              value=st.session_state.get('ac_conso', 1.5))
    with col2:
        puissance = st.number_input("Puissance frigorifique (kW)", 
                                 min_value=0.1, 
                                 max_value=20.0, 
                                 value=st.session_state.get('ac_froid', 3.5))
    
    inverter = st.selectbox("Technologie Inverter", 
                          ["Oui", "Non"], 
                          index=0 if st.session_state.get('ac_inverter', True) else 1)
    
    if st.button("Valider les données manuelles"):
        st.session_state.ac_modele = modele or "Modèle inconnu"
        st.session_state.ac_conso = conso
        st.session_state.ac_froid = puissance
        st.session_state.ac_inverter = inverter == "Oui"
        st.session_state.ac_data_ok = True
        st.experimental_rerun()

# Affichage des données validées
if st.session_state.ac_data_ok:
    st.success("Données techniques validées ✅")
    cols = st.columns(3)
    cols[0].metric("Consommation", f"{st.session_state.ac_conso} kW")
    cols[1].metric("Puissance frigorifique", f"{st.session_state.ac_froid} kW")
    cols[2].metric("Technologie", "Inverter" if st.session_state.ac_inverter else "Standard")
