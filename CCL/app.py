import streamlit as st
import uuid
from models import Playbook, PlaybookBullet, LogEntry, Student
from database import db
from agents import Generator, Reflector, Curator

# Initialize session state for playbook and chat history
if "playbook" not in st.session_state:
    st.session_state.playbook = Playbook(bullets=[
        PlaybookBullet(id=str(uuid.uuid4()), rule="Always be polite and professional.")
    ])
if "messages" not in st.session_state:
    st.session_state.messages = []

# Instantiate agents
generator = Generator()
reflector = Reflector()
curator = Curator()

st.set_page_config(page_title="Student Information Chatbot", layout="wide")

tab1, tab2 = st.tabs(["Student Chat", "Admin Portal"])

with tab1:
    st.header("Student Information Bot")
    
    # Render chat history
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Provide feedback button for the latest assistant message
            if msg["role"] == "assistant" and i == len(st.session_state.messages) - 1:
                if st.button("Mark as Invalid", key=f"invalid_{i}"):
                    evaluation = reflector.evaluate("invalid")
                    if evaluation == "harmful":
                        user_query = st.session_state.messages[i-1]["content"] if i > 0 else ""
                        bot_response = msg["content"]
                        
                        fix = curator.draft_fix(user_query, bot_response)
                        
                        log_entry = LogEntry(
                            id=str(uuid.uuid4()),
                            query=user_query,
                            response=bot_response,
                            suggested_fix=fix
                        )
                        db.save_invalid_log(log_entry)
                        st.error("Reported to Admin. A potential fix has been queued.")

    # Chat input
    if prompt := st.chat_input("Ask a question about the college or ask about your user data..."):
        
        # 1) Memory confirmation interception logic
        if len(st.session_state.messages) >= 1:
            last_bot_msg = st.session_state.messages[-1]["content"]
            if "Are you sure? I will remember:" in last_bot_msg:
                user_confimation = prompt.lower().strip()
                if user_confimation in ["yes", "yeah", "yep", "sure", "of course", "yes i am sure"]:
                    # Extract the fact
                    fact_str = last_bot_msg.split("I will remember:")[1].strip()
                    db.add_learned_fact(fact_str)
                    
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    with st.chat_message("user"): st.markdown(prompt)
                    
                    response = f"Got it! I have saved: '{fact_str}' to my knowledge base."
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    with st.chat_message("assistant"): st.markdown(response)
                    st.rerun()

        # 2) Standard chat flow
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            # Pass the entirely history for context (up to 3 mapped inside DB/Agents)
            context = db.retrieve_context(st.session_state.messages)
            output = generator.generate(st.session_state.messages, st.session_state.playbook, context)
            
            st.markdown(output.response)
            if output.sources:
                st.caption(f"Sources: {', '.join(output.sources)}")
                
        st.session_state.messages.append({"role": "assistant", "content": output.response})
        st.rerun()

with tab2:
    st.header("Admin Portal")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Add General Knowledge")
        with st.form("add_gen_knowledge"):
            topic_input = st.text_input("Topic/Keyword")
            info_input = st.text_area("Information")
            if st.form_submit_button("Add Event/Info"):
                if topic_input and info_input:
                    db.add_general_info(topic_input, info_input)
                    st.success(f"Added new general info for: {topic_input}")
                    
        st.subheader("Current Learned Knowledge")
        learned_facts = db.get_learned_facts()
        if not learned_facts:
            st.info("No learned facts yet.")
        for fact in learned_facts:
            st.markdown(f"- {fact.get('fact', '')}")

    with col2:
        st.subheader("Add Student")
        with st.form("add_student"):
            new_s_name = st.text_input("Student Name")
            new_s_key = st.text_input("Secret Key (e.g. SEC123)")
            new_s_major = st.text_input("Major")
            new_s_gpa = st.number_input("GPA", min_value=0.0, max_value=4.0, value=3.0)
            new_s_year = st.number_input("Enrollment Year", step=1, value=2024)
            
            if st.form_submit_button("Add Student Database Record"):
                if new_s_name and new_s_key:
                    student = Student(name=new_s_name, secret_key=new_s_key, gpa=new_s_gpa, major=new_s_major, enrollment_year=new_s_year)
                    db.add_student(student)
                    st.success(f"Added student {new_s_name} with key {new_s_key}")
                    
        st.subheader("Current DB Students Check")
        st.info(f"There are currently {db.get_students_count()} students in the database.")

    st.divider()
    
    # Existing ACE Admin tools
    st.subheader("Playbook & Safety Logging")
    with st.expander("View Current Playbook Rules"):
        for b in st.session_state.playbook.bullets:
            st.markdown(f"- {b.rule}")
            
    st.subheader("Invalid Interaction Logs & Fixes")
    logs = db.get_admin_logs()
    
    if not logs:
        st.info("No reported issues currently in the queue.")
    else:
        for log in logs:
            with st.expander(f"Issue: {log.query}"):
                st.write("**Bot Response:**", log.response)
                
                if log.suggested_fix:
                    st.write("**Curator Suggestion:**")
                    st.json(log.suggested_fix.model_dump())
                    
                    admin_edited_rule = st.text_area(
                        "Admin Comment / Edit Rule before approving:", 
                        value=log.suggested_fix.new_rule, 
                        key=f"edit_{log.id}"
                    )
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Approve Curator Fix", key=f"approve_{log.id}"):
                            if log.suggested_fix.action == "ADD" and log.suggested_fix.new_rule:
                                new_bullet = PlaybookBullet(id=str(uuid.uuid4()), rule=admin_edited_rule)
                                st.session_state.playbook.bullets.append(new_bullet)
                                db.delete_log(log.id)
                                st.success("Rule added!")
                                st.rerun()
                    with c2:
                        if st.button("Delete Log", key=f"delete_{log.id}"):
                            db.delete_log(log.id)
                            st.rerun()