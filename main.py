        # ── 생중량 분포 (박스플롯) ──
        st.markdown("### 📦 생중량 분포 (박스플롯)")
        if GW_COL and GW_COL in df_grt.columns:
            gw_data = df_grt[GW_COL].dropna()
            q25 = gw_data.quantile(0.25)
            q75 = gw_data.quantile(0.75)

            # ✦✦✦ 수정: px.box에 문자열 리스트가 아닌 DataFrame을 넘김 ✦✦✦
            box_df = pd.DataFrame({
                'group': [GW_COL] * len(gw_data),
                'value': gw_data.values,
            })

            fig_box = px.box(
                data_frame=box_df,
                x='group',
                y='value',
                labels={'group': GW_COL, 'value': '생중량 (g)'},
                boxmean=True,
            )
            fig_box.update_traces(
                marker_color='#4ecdc4',
                marker=dict(size=4),
                line_color='#1a535c',
            )
            fig_box.add_hline(
                y=q75, line_dash="dot", line_color='#ff6b6b',
                annotation_text=f"상위 25% 기준: {q75:.2f} g",
                annotation_position="top right",
                annotation_font=dict(size=11, color='#ff6b6b'),
            )
            fig_box.add_hline(
                y=q25, line_dash="dot", line_color='#6c5ce7',
                annotation_text=f"하위 25% 기준: {q25:.2f} g",
                annotation_position="bottom right",
                annotation_font=dict(size=11, color='#6c5ce7'),
            )
            fig_box.update_layout(
                height=360,
                margin=dict(l=40, r=60, t=30, b=40),
                font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=12),
                xaxis=dict(showticklabels=False),
                yaxis=dict(title='생중량 (g)', showgrid=True, gridcolor='#f0f0f0'),
                showlegend=False,
            )
            st.plotly_chart(fig_box, key="growth_box", width='stretch')

            iqr = q75 - q25
            cv_gw = (gw_data.std() / gw_data.mean() * 100) if gw_data.mean() else float('nan')
            st.markdown(
                f"**생중량 분포 요약**\n"
                f"- 개체 수: {len(gw_data)}개체\n"
                f"- 1사분위(Q1, 하위 25% 기준): **{q25:.2f} g**\n"
                f"- 3사분위(Q3, 상위 25% 기준): **{q75:.2f} g**\n"
                f"- 사분위범위(IQR): {iqr:.2f} g\n"
                f"- 변동계수(CV): **{cv_gw:.1f}%** {TERM_CV}\n"
                f"\n"
                f"💡 붉은 점선(상위 25% 기준) 이상 개체가 상위 25%, "
                f"보라 점선(하위 25% 기준) 이하 개체가 하위 25%입니다."
            )
        else:
            st.warning("⚠️ '생중량(g)' 열이 없어 분포도를 표시할 수 없습니다.")
