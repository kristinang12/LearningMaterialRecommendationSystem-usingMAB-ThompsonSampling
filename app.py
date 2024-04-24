from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import psycopg2, random, os, uuid
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.secret_key = 'keyni'

# Get the database URL from an environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')

# Connect to the database using the DATABASE_URL environment variable
conn = psycopg2.connect(DATABASE_URL, sslmode='prefer')

cur = conn.cursor()

#postgres://lmrecommendationsystem_db_user:sg05UcW4YQS53HpmfmTeamDkqtXM8aIF@dpg-co95ksi0si5c7396oqu0-a/lmrecommendationsystem_db
#postgres://lmrecommendationsystem_db_user:sg05UcW4YQS53HpmfmTeamDkqtXM8aIF@dpg-co95ksi0si5c7396oqu0-a.ohio-postgres.render.com/lmrecommendationsystem_db
#sg05UcW4YQS53HpmfmTeamDkqtXM8aIF
#Host name/address: dpg-co95ksi0si5c7396oqu0-a.ohio-postgres.render.com
#Port: 5432
#Maintenance database: lmrecommendationsystem_db
#Username: lmrecommendationsystem_db_user
#Password: sg05UcW4YQS53HpmfmTeamDkqtXM8aIF


def generate_unique_session_key():
    return str(uuid.uuid4())

def regretCalculation(optimal, arm_id_r, meanreward_r, session_key, meanreward_s=None, arm_id_s=None):
    if arm_id_s is not None:
        regret_s = optimal - meanreward_s
        regret_r = optimal - meanreward_r
        total_regret = (regret_s + regret_r) / 2
        cur.execute("INSERT INTO regretcalculationts (arm_id_s,optimalarm, selectedarm_s, regret_s, arm_id_r, selectedarm_r, regret_r, total_regret, session_key) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (arm_id_s, optimal, meanreward_s, regret_s, arm_id_r, meanreward_r, regret_r, total_regret, session_key))
    else:
        regret_r = optimal - meanreward_r
        total_regret = regret_r
        cur.execute("INSERT INTO regretcalculationts (arm_id_r,optimalarm, selectedarm_r, regret_r, total_regret, session_key) VALUES (%s, %s, %s, %s, %s, %s)", (arm_id_r,optimal,  meanreward_r, regret_r, total_regret, session_key))
    
    conn.commit()

def rewardCalculation(arm_id_r, session_key, arm_id_s=None):
    cur.execute("SELECT alpha, beta, average_reward FROM armsrewardts WHERE arm_id = %s", (arm_id_r,))
    row_r = cur.fetchone()
    
    if row_r is not None:
        alpha_r, beta_r, meanreward_r = row_r
        meanreward_s = 0  # Initialize meanreward_s
        
        if arm_id_s is not None:
            cur.execute("SELECT alpha, beta, average_reward FROM armsrewardts WHERE arm_id = %s", (arm_id_s,))
            row_s = cur.fetchone()
            
            if row_s is not None:
                alpha_s, beta_s, meanreward_s = row_s
                meanreward_s = alpha_s / (alpha_s + beta_s)
                total_meanreward = (meanreward_s + meanreward_r) / 2
                cur.execute("INSERT INTO rewardcalculationts (arm_id_s, alpha_s, beta_s, meanreward_s, arm_id_r, alpha_r, beta_r, meanreward_r, total_meanreward, session_key) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (arm_id_s, alpha_s, beta_s, meanreward_s, arm_id_r, alpha_r, beta_r, meanreward_r, total_meanreward, session_key))
                
                cur.execute("SELECT average_reward FROM armsrewardts ORDER BY average_reward DESC LIMIT 1")
                whatOptimal = cur.fetchone()
                
                if whatOptimal: 
                    optimal = whatOptimal[0]
                    regretCalculation(optimal, arm_id_r, meanreward_r, session_key, meanreward_s, arm_id_s)
                    
        else:   
            total_meanreward = meanreward_r
            cur.execute("INSERT INTO rewardcalculationts (arm_id_r, alpha_r, beta_r, meanreward_r, total_meanreward, session_key) VALUES (%s, %s, %s, %s, %s, %s)", (arm_id_r, alpha_r, beta_r, meanreward_r, total_meanreward, session_key))
            
            cur.execute("SELECT average_reward FROM armsrewardts ORDER BY average_reward DESC LIMIT 1")
            optimal = cur.fetchone()[0]
            
            regretCalculation(optimal, arm_id_r, meanreward_r, session_key, meanreward_s, arm_id_s)

    conn.commit()

def observereward(arm_id, session_key):
    cur.execute("SELECT id, arm_id_s, alpha_s, beta_s, meanreward_s, arm_id_r, alpha_r, beta_r, meanreward_r FROM rewardcalculationts WHERE session_key <= %s ORDER BY id DESC", (session_key,))
    rows = cur.fetchall()

    if rows:
        id, arm_id_search, alpha_s, beta_s, meanreward_s, arm_id_r, alpha_r, beta_r, meanreward_r = rows[0]  # Get the first row
        if arm_id == arm_id_search:
            alpha_s += 1
            beta_s -= 1
            meanreward_s = alpha_s / (alpha_s+beta_s)
            total_meanreward = (meanreward_r + meanreward_s)/2
            reward_s = 1
            cur.execute("UPDATE rewardcalculationts SET reward_s = %s, alpha_s = %s, beta_s = %s, meanreward_s = %s, total_meanreward =%s WHERE session_key = %s", (reward_s, alpha_s, beta_s, meanreward_s, total_meanreward, session_key))
            
            cur.execute("SELECT meanreward_r, meanreward_s FROM rewardcalculationts WHERE session_key <= %s ORDER BY id DESC", (session_key,))
            whatOptimal = cur.fetchone()

            if whatOptimal: 
                meanreward_r_main, meanreward_s_main = whatOptimal
                if meanreward_s_main > meanreward_r_main:
                    cur.execute("SELECT optimalarm, regret_r FROM regretcalculationts WHERE session_key = %s", (session_key,))
                    regretrows = cur.fetchone()
                    if regretrows:
                        optimal_arm, regret_r = regretrows
                        
                        if  meanreward_s_main > optimal_arm:
                            optimal = meanreward_s_main
                            regret_s = optimal - meanreward_s
                            total_regret = (regret_r + regret_s)/2
                            cur.execute("UPDATE regretcalculationts SET optimalarm=%s, selectedarm_s=%s, regret_s = %s, total_regret=%s WHERE session_key=%s", (optimal, meanreward_s, regret_s,  total_regret, session_key))
                        else:
                            optimal = optimal_arm
                            regret_s = optimal - meanreward_s
                            total_regret = (regret_r + regret_s)/2
                            cur.execute("UPDATE regretcalculationts SET optimalarm=%s, selectedarm_s=%s, regret_s = %s, total_regret=%s WHERE session_key=%s", (optimal, meanreward_s, regret_s, total_regret, session_key))
                    
                else:
                    cur.execute("SELECT optimalarm, regret_r FROM regretcalculationts WHERE session_key = %s", (session_key,))
                    regretrows = cur.fetchone()
                    if regretrows:
                        optimal_arm, regret_r = regretrows

                        if meanreward_r_main > optimal_arm:
                            optimal = meanreward_r_main
                            regret_s = optimal - meanreward_s
                            total_regret = (regret_r + regret_s)/2
                            cur.execute("UPDATE regretcalculationts SET optimalarm=%s, selectedarm_s=%s, regret_s = %s, selectedarm_r=%s, regret_r=%s, total_regret=%s WHERE session_key=%s", (optimal, meanreward_s, regret_s, meanreward_r, regret_r, total_regret, session_key))
                        else:
                            optimal = meanreward_r_main
                            regret_s = optimal - meanreward_s
                            total_regret = (regret_r + regret_s)/2
                            cur.execute("UPDATE regretcalculationts SET optimalarm=%s, selectedarm_s=%s, regret_s = %s, selectedarm_r=%s, regret_r=%s, total_regret=%s WHERE session_key=%s", (optimal, meanreward_s, regret_s, meanreward_r, regret_r, total_regret, session_key))
        else:
            alpha_r += 1
            beta_r -= 1
            meanreward_r = alpha_r / (alpha_r +beta_r)
            total_meanreward = meanreward_r
            reward_r = 1
            cur.execute("UPDATE rewardcalculationts SET reward_r = %s, alpha_r = %s, beta_r = %s, meanreward_r = %s, total_meanreward =%s  WHERE session_key = %s", (reward_r, alpha_r, beta_r, meanreward_r, total_meanreward, session_key))
            
            cur.execute("SELECT meanreward_r, meanreward_s FROM rewardcalculationts WHERE session_key <= %s ORDER BY id DESC", (session_key,))
            whatOptimal = cur.fetchone()

            if whatOptimal: 
                meanreward_r_main, meanreward_s_main = whatOptimal
                if meanreward_r_main > meanreward_s_main:
                    cur.execute("SELECT optimalarm, regret_r FROM regretcalculationts WHERE session_key = %s", (session_key,))
                    regretrows = cur.fetchone()
                    
                    if regretrows:
                        optimal_arm, regret_r = regretrows
                        if meanreward_r_main > optimal_arm:
                            optimal = meanreward_r_main
                            regret_r = optimal - meanreward_r
                            total_regret = regret_r
                            cur.execute("UPDATE regretcalculationts SET optimalarm=%s, selectedarm_r=%s, regret_r=%s, total_regret=%s WHERE session_key=%s", (optimal, meanreward_r, regret_r, total_regret, session_key))
                        else:
                            optimal = optimal_arm
                            regret_r = optimal - meanreward_r
                            total_regret = regret_r 
                            cur.execute("UPDATE regretcalculationts SET optimalarm=%s, selectedarm_r=%s, regret_r=%s, total_regret=%s WHERE session_key=%s", (optimal, meanreward_r, regret_r, total_regret, session_key))
                else:
                    cur.execute("SELECT optimalarm, regret_r FROM regretcalculationts WHERE session_key = %s", (session_key,))
                    regretrows = cur.fetchone()
                    
                    if regretrows:
                        optimal_arm, regret_r = regretrows
                        if meanreward_r_main > optimal_arm:
                            optimal = meanreward_r_main
                            regret_r = optimal - meanreward_r
                            total_regret = regret_r
                            cur.execute("UPDATE regretcalculationts SET optimalarm=%s, selectedarm_r=%s, regret_r=%s, total_regret=%s WHERE session_key=%s", (optimal, meanreward_r, regret_r, total_regret, session_key))
                        else:
                            optimal = optimal_arm
                            regret_r = optimal - meanreward_r
                            total_meanreward = regret_r
                            cur.execute("UPDATE regretcalculationts SET optimalarm=%s, selectedarm_r=%s, regret_r=%s, total_regret=%s WHERE session_key=%s", (optimal, meanreward_r, regret_r, total_regret, session_key))

        conn.commit()
    
def updateReward(arm_id):
    cur.execute("SELECT alpha, beta, average_reward FROM armsrewardts WHERE arm_id = %s", (arm_id,))
    row = cur.fetchone()
    
    if row is not None:
        alpha, beta, average_reward = row
        beta -= 1
        alpha += 1
        average_reward = alpha / (beta+alpha) if alpha > 0 else 0
        cur.execute("UPDATE armsrewardts SET alpha = %s, beta = %s, average_reward = %s WHERE arm_id = %s", (alpha, beta, average_reward, arm_id))
        conn.commit()
        
def updateArmSelection(arm_id):

    cur.execute("SELECT alpha, beta, average_reward FROM armsrewardts WHERE arm_id = %s", (arm_id,))
    row = cur.fetchone()
    
    if row:
        alpha, beta, average_reward = row

        beta += 1
        
        average_reward = alpha / (beta+alpha) if alpha > 0 else 0
        
        cur.execute("UPDATE armsrewardts SET alpha = %s, beta= %s, average_reward = %s  WHERE arm_id = %s", (alpha, beta, average_reward, arm_id))
        
    conn.commit()

def select_arm():
    num_arms = 10
    sampled_probs = []

    # If there is no search query or no suitable arms found for the search query, fall back to Thompson Sampling
    if not sampled_probs:
        for arm_id in range(1, num_arms + 1):
            cur.execute("SELECT alpha, beta FROM armsrewardts WHERE arm_id = %s", (arm_id,))
            row = cur.fetchone()

            if row is not None:
                alpha, beta = row
                sampled_prob = random.betavariate(alpha, beta)
                sampled_probs.append((arm_id, sampled_prob))

    # Select an arm based on the expected rewards
    if sampled_probs:
        arm_id = max(sampled_probs, key=lambda x: x[1])[0]
        return arm_id

    # If no arm is selected, return a default recommendation
    return 1  # Default recommendation arm_id
@app.route('/', methods=['GET', 'POST'])
def index():
    no_results_message = ""
    show_results_label = False
    recommended_lm_titles = []
    search_recommendation = []
    session['key'] = generate_unique_session_key()  # Use a function to generate a unique session key

    session_key = session.get('key')
    
    arm_id_r = select_arm()
    arm_id_s = None
    # Retrieve the learning material titles for the selected arm
    cur.execute("SELECT lm_title FROM arms10 WHERE arm_id = %s", (arm_id_r,))
    rows = cur.fetchall()
    arm_recommendations = [row[0] for row in rows] if cur.rowcount > 0 else []
    recommended_lm_titles.extend(arm_recommendations)

    if arm_id_r:
        updateArmSelection(arm_id_r)
    
    if request.method == 'POST':
        search_query = request.form.get('search_query', '')  # Use get() to avoid KeyError

        # Check if the search query is not empty
        if search_query.strip():
            # Check if the selected arm matches the search result
            cur.execute("SELECT arm_id FROM armsrewardts WHERE lower(lm_title) LIKE lower(%s) ORDER BY average_reward DESC LIMIT 1",
                        ('%{}%'.format(search_query),))
            arm_id_s = cur.fetchone()[0] if cur.rowcount > 0 else None

            if arm_id_s:
                cur.execute("SELECT lm_title FROM armsrewardts WHERE arm_id = %s", (arm_id_s,))
                rows = cur.fetchall()
                search_results = [row[0] for row in rows] if cur.rowcount > 0 else []
                
                updateArmSelection(arm_id_s)
                
                if not search_results:
                    no_results_message = "No search results found. Try recommended learning material."
                else:
                    show_results_label = True

                search_recommendation.extend(search_results)
            else:
                no_results_message = "No search results found. Try recommended learning material."
                
    # Call rewardCalculation outside the if block to ensure it's always called
    if arm_id_r and arm_id_s:
        rewardCalculation(arm_id_r, session_key, arm_id_s)
    else:
        rewardCalculation(arm_id_r, session_key)
 
    return render_template('index.html', no_results_message=no_results_message,
                           show_results_label=show_results_label, recommended_lm_titles=recommended_lm_titles,
                           search_recommendation=search_recommendation, session_key=session_key)

@app.route('/click_lm/<lm_title>', methods=['GET'])
def click_lm(lm_title):
    session_key = session.get('key')
    # Retrieve the description of the clicked learning material
    cur.execute("SELECT description FROM arms10 WHERE lm_title = %s", (lm_title,))
    row = cur.fetchone()
    description = row[0] if row else "Description not found"

    # Check if the update has already been performed twice for this learning material
    update_count_key = 'update_count_' + lm_title
    update_count = session.get(update_count_key, 0)
    
    if update_count > 1:
        # Render the learning material description page without updating the database
        return render_template('material.html', description=description)
    # Update the armsreward table with the arm_id
    cur.execute("SELECT arm_id FROM armsrewardts WHERE lm_title = %s", (lm_title,))
    row = cur.fetchone()
    arm_id_r = row[0] if row else None
    if arm_id_r is not None:
        updateReward(arm_id_r)
        observereward(arm_id_r, session_key)
        
    session[update_count_key] = update_count + 2

    # Render the learning material description page
    return render_template('material.html', description=description)

@app.route('/click_resultquery/<lm_result>', methods=['GET'])
def click_searchquery(lm_result):
    session_key = session.get('key')
    # Retrieve the description of the clicked learning material
    cur.execute("SELECT description FROM arms10 WHERE lm_title = %s", (lm_result,))
    row = cur.fetchone()
    description = row[0] if row else "Description not found"

    # Check if the update has already been performed twice for this learning material
    update_count_key = 'update_count_' + lm_result
    update_count = session.get(update_count_key, 0)
    
    if update_count > 1:
        # Render the learning material description page without updating the database
        return render_template('material.html', description=description)
    # Update the armsreward table with the arm_id
    cur.execute("SELECT arm_id FROM armsrewardts WHERE lm_title = %s", (lm_result,))
    row = cur.fetchone()
    arm_id_s = row[0] if row else None
    if arm_id_s is not None:
        updateReward(arm_id_s)
        observereward(arm_id_s, session_key)
        
    session[update_count_key] = update_count + 2

    # Render the learning material description page
    return render_template('material.html', description=description)

@app.route('/reset_session', methods=['GET'])
def reset_session():
    session.clear()
    return '', 204

if __name__ == '__main__':
    # Use the PORT environment variable if available, otherwise default to 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)