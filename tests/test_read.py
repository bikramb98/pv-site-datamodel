"""Test read functions."""

import datetime as dt
import uuid
from typing import List

import pytest
from sqlalchemy.orm import Query

from pvsite_datamodel import (
    ForecastSQL,
    ForecastValueSQL,
    SiteGroupSQL,
    SiteSQL,
    StatusSQL,
    UserSQL,
)
from pvsite_datamodel.pydantic_models import LatitudeLongitudeLimits
from pvsite_datamodel.read import (
    get_all_site_groups,
    get_all_sites,
    get_all_users,
    get_latest_forecast_values_by_site,
    get_latest_status,
    get_pv_generation_by_sites,
    get_pv_generation_by_user_uuids,
    get_site_by_client_site_id,
    get_site_by_client_site_name,
    get_site_by_uuid,
    get_site_group_by_name,
    get_sites_by_country,
    get_sites_from_user,
    get_user_by_email,
)
from pvsite_datamodel.write.user_and_site import create_site_group, create_user


class TestGetAllSites:
    """Tests for the get_all_sites function."""

    def test_returns_all_sites(self, sites, db_session):
        out = get_all_sites(db_session)

        assert len(out) == len(sites)

        site = [s for s in sites if s.site_uuid == out[0].site_uuid][0]
        assert out[0] == site

        # check uuid is in order
        assert out[1].site_uuid > out[0].site_uuid
        assert out[2].site_uuid > out[1].site_uuid
        assert out[3].site_uuid > out[2].site_uuid

        # check uuid is in order
        assert out[1].site_uuid > out[0].site_uuid
        assert out[2].site_uuid > out[1].site_uuid
        assert out[3].site_uuid > out[2].site_uuid


class TestGetSitesByCountry:
    """Tests for the get_sites_by_country function."""

    def test_returns_correct_uk_sites(self, make_sites_for_country, db_session):
        country = "uk"
        sites = make_sites_for_country(country)
        out = get_sites_by_country(db_session, country)

        assert len(out) == len(sites)
        assert all([o.country == country for o in out])

    def test_returns_correct_india_sites(self, make_sites_for_country, db_session):
        country = "india"
        sites = make_sites_for_country(country)
        out = get_sites_by_country(db_session, country)

        assert len(out) == len(sites)
        assert all([o.country == country for o in out])

    def test_returns_no_sites_for_unknown_country(self, make_sites_for_country, db_session):
        _ = make_sites_for_country("uk")
        out = get_sites_by_country(db_session, "nocountry")

        assert len(out) == 0


class TestGetSiteByUUID:
    """Tests for the get_site_by_uuid function."""

    def tests_gets_site_for_existing_uuid(self, sites, db_session):
        site = get_site_by_uuid(session=db_session, site_uuid=sites[0].site_uuid)

        assert site == sites[0]

    def test_raises_error_for_nonexistant_site(self, sites, db_session):
        with pytest.raises(KeyError):
            _ = get_site_by_uuid(session=db_session, site_uuid=uuid.uuid4())

    def test_get_site_by_client_site_id(self, sites, db_session):
        site = get_site_by_client_site_id(
            session=db_session,
            client_name=sites[0].client_site_name,
            client_site_id=sites[0].client_site_id,
        )

        assert site == sites[0]

    def test_get_site_by_client_site_name(self, sites, db_session):
        site = get_site_by_client_site_name(
            session=db_session,
            client_name="test_client",
            client_site_name=sites[0].client_site_name,
        )

        assert site == sites[0]


class TestGetUserByEmail:
    """Test for get_user_by_email function"""

    def test_get_user_by_email_no_users(self, db_session):
        user = get_user_by_email(session=db_session, email="test@test.com")
        assert user.email == "test@test.com"
        assert len(db_session.query(UserSQL).all()) == 1

    def test_get_user_by_email_with_users(self, db_session):
        site_group = create_site_group(db_session=db_session)
        user = create_user(
            session=db_session, site_group_name=site_group.site_group_name, email="test_1@test.com"
        )
        user = create_user(
            session=db_session, site_group_name=site_group.site_group_name, email="test_2@test.com"
        )

        user = get_user_by_email(session=db_session, email="test_1@test.com")
        assert user.email == "test_1@test.com"
        assert len(db_session.query(UserSQL).all()) == 2


class TestGetPVGenerationByUser:
    """Tests for the get_pv_generation_by_client function."""

    def test_returns_all_generations_without_input_user(self, generations, db_session):
        generations = get_pv_generation_by_user_uuids(session=db_session)

        assert len(generations) == 40

    def test_returns_all_generations_for_input_user(self, generations, db_session):
        # associate site to one user
        site: SiteSQL = db_session.query(SiteSQL).first()
        site_group = create_site_group(db_session=db_session)
        user = create_user(
            session=db_session, site_group_name=site_group.site_group_name, email="test@test.com"
        )
        site_group.sites.append(site)

        generations = get_pv_generation_by_user_uuids(
            session=db_session, user_uuids=[user.user_uuid]
        )

        assert len(generations) == 10

    def test_returns_all_generations_in_datetime_window(self, generations, db_session):
        # associate site to one user
        site: SiteSQL = db_session.query(SiteSQL).first()
        site_group = create_site_group(db_session=db_session)
        user = create_user(
            session=db_session, site_group_name=site_group.site_group_name, email="test@test.com"
        )
        site_group.sites.append(site)

        window_lower: dt.datetime = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=7)
        window_upper: dt.datetime = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=8)

        generations = get_pv_generation_by_user_uuids(
            session=db_session,
            user_uuids=[user.user_uuid],
            start_utc=window_lower,
            end_utc=window_upper,
        )

        assert len(generations) == 7


class TestGetPVGenerationBySites:
    """Tests for the get_pv_generation_by_sites function."""

    def test_gets_generation_for_single_input_site(self, generations, db_session):
        query: Query = db_session.query(SiteSQL)
        site: SiteSQL = query.first()

        generations = get_pv_generation_by_sites(session=db_session, site_uuids=[site.site_uuid])

        assert len(generations) == 10
        assert generations[0].start_utc is not None
        assert generations[0].site is not None

    def test_gets_generation_for_multiple_input_sites(self, generations, db_session):
        query: Query = db_session.query(SiteSQL)
        sites: List[SiteSQL] = query.all()

        generations = get_pv_generation_by_sites(
            session=db_session, site_uuids=[site.site_uuid for site in sites]
        )

        assert len(generations) == 10 * len(sites)

    def test_returns_empty_list_for_no_input_sites(self, generations, db_session):
        generations = get_pv_generation_by_sites(session=db_session, site_uuids=[])

        assert len(generations) == 0

    def test_gets_generation_for_multiple_sum_total(self, generations, db_session):
        query: Query = db_session.query(SiteSQL)
        sites: List[SiteSQL] = query.all()

        generations = get_pv_generation_by_sites(
            session=db_session, site_uuids=[site.site_uuid for site in sites], sum_by="total"
        )

        assert len(generations) == 10
        assert generations[0].power_kw == 4
        assert generations[1].power_kw == 8
        assert (generations[2].start_utc - generations[1].start_utc).seconds == 60

    def test_gets_generation_for_multiple_sum_gsp(self, generations, db_session):
        query: Query = db_session.query(SiteSQL)
        sites: List[SiteSQL] = query.all()

        generations = get_pv_generation_by_sites(
            session=db_session, site_uuids=[site.site_uuid for site in sites], sum_by="gsp"
        )
        assert len(generations) == 10 * len(sites)

    def test_gets_generation_for_multiple_sum_dno(self, generations, db_session):
        query: Query = db_session.query(SiteSQL)
        sites: List[SiteSQL] = query.all()

        generations = get_pv_generation_by_sites(
            session=db_session, site_uuids=[site.site_uuid for site in sites], sum_by="dno"
        )
        assert len(generations) == 10 * len(sites)

    def test_gets_generation_for_multiple_sum_error(self, generations, db_session):
        query: Query = db_session.query(SiteSQL)
        sites: List[SiteSQL] = query.all()

        with pytest.raises(ValueError):  # noqa
            _ = get_pv_generation_by_sites(
                session=db_session, site_uuids=[site.site_uuid for site in sites], sum_by="blah"
            )


class TestGetLatestStatus:
    """Tests for the get_latest_status function."""

    def test_gets_latest_status_when_exists(self, statuses, db_session):
        status: StatusSQL = get_latest_status(db_session)

        assert status.message == "Status 3"


def _add_forecast_value(session, forecast, power: int, ts):
    fv = ForecastValueSQL(
        forecast_uuid=forecast.forecast_uuid,
        forecast_power_kw=power,
        start_utc=ts,
        end_utc=ts + dt.timedelta(minutes=5),
    )
    session.add(fv)


def test_get_latest_forecast_values(db_session, sites):
    site_uuids = [site.site_uuid for site in db_session.query(SiteSQL.site_uuid).limit(2)]

    s1, s2 = site_uuids

    forecast_version = "123"

    # Make sure we have some forecasts in the DB
    s1_f1 = ForecastSQL(
        site_uuid=s1,
        forecast_version=forecast_version,
        timestamp_utc=dt.datetime(2000, 1, 1),
    )
    s1_f2 = ForecastSQL(
        site_uuid=s1,
        forecast_version=forecast_version,
        timestamp_utc=dt.datetime(2000, 1, 1, 0, 10),
    )
    s2_f1 = ForecastSQL(
        site_uuid=s2,
        forecast_version=forecast_version,
        timestamp_utc=dt.datetime(2000, 1, 1),
    )

    db_session.add_all([s1_f1, s1_f2, s2_f1])
    db_session.commit()

    d0 = dt.datetime(2000, 1, 1, 0)
    d1 = dt.datetime(2000, 1, 1, 1)
    d2 = dt.datetime(2000, 1, 1, 2)
    d3 = dt.datetime(2000, 1, 1, 3)
    d4 = dt.datetime(2000, 1, 1, 4)

    # site 1 forecast 1
    _add_forecast_value(db_session, s1_f1, 1.0, d0)
    _add_forecast_value(db_session, s1_f1, 2.0, d1)
    _add_forecast_value(db_session, s1_f1, 3.0, d2)

    # site 1 forecast 2
    _add_forecast_value(db_session, s1_f2, 4.0, d2)
    _add_forecast_value(db_session, s1_f2, 5.0, d3)
    _add_forecast_value(db_session, s1_f2, 6.0, d4)

    # Site 2 forecast 1
    _add_forecast_value(db_session, s2_f1, 7.0, d0)
    _add_forecast_value(db_session, s2_f1, 8.0, d1)
    _add_forecast_value(db_session, s2_f1, 9.0, d2)
    db_session.commit()

    latest_forecast = get_latest_forecast_values_by_site(db_session, site_uuids, d1)

    expected = {
        s1: [(d1, 2), (d2, 4), (d3, 5), (d4, 6)],
        s2: [(d1, 8), (d2, 9)],
    }

    assert list(sorted(latest_forecast.keys())) == list(sorted(expected.keys()))

    for site_uuid, forecast_values in latest_forecast.items():
        # Format the values in a way that we can compare them.
        values_as_tuple = [(v.start_utc, v.forecast_power_kw) for v in forecast_values]

        assert values_as_tuple == expected[site_uuid]

    latest_forecast = get_latest_forecast_values_by_site(
        session=db_session, site_uuids=site_uuids, start_utc=d1, sum_by="total"
    )
    assert len(latest_forecast) == 4

    latest_forecast = get_latest_forecast_values_by_site(
        session=db_session, site_uuids=site_uuids, start_utc=d1, sum_by="dno"
    )
    assert len(latest_forecast) == 4 + 2  # 4 from site 1, 2 from site 2

    latest_forecast = get_latest_forecast_values_by_site(
        session=db_session, site_uuids=site_uuids, start_utc=d2, sum_by="gsp"
    )
    assert len(latest_forecast) == 3 + 1  # 3 from site 1, 1 from site 2

    with pytest.raises(ValueError):  # noqa
        _ = get_latest_forecast_values_by_site(
            session=db_session, site_uuids=site_uuids, start_utc=d2, sum_by="bla"
        )


def test_get_site_group_by_name(db_session):
    site_group = SiteGroupSQL(site_group_name="test")
    db_session.add(site_group)
    db_session.commit()

    result = get_site_group_by_name(db_session, "test")

    assert result == site_group


def test_get_site_group_by_name_new_group(db_session):
    _ = get_site_group_by_name(db_session, "test")

    assert len(db_session.query(SiteGroupSQL).all()) == 1


def test_get_all_users(db_session):
    users = get_all_users(session=db_session)
    # assert
    assert len(users) == 0


def test_get_all_site_groups(db_session):
    site_groups = get_all_site_groups(session=db_session)
    # assert
    assert len(site_groups) == 0


def test_get_site_from_user(db_session, user_with_sites):
    sites = get_sites_from_user(session=db_session, user=user_with_sites)
    assert len(sites) > 0


def test_get_site_list_max(db_session, user_with_sites):
    # examples sites are at 51,3
    lat_lon = LatitudeLongitudeLimits(latitude_max=50, longitude_max=4)
    sites = get_sites_from_user(session=db_session, user=user_with_sites, lat_lon_limits=lat_lon)
    assert len(sites) == 0

    lat_lon = LatitudeLongitudeLimits(latitude_max=52, longitude_max=2)
    sites = get_sites_from_user(session=db_session, user=user_with_sites, lat_lon_limits=lat_lon)
    assert len(sites) == 0

    lat_lon = LatitudeLongitudeLimits(latitude_max=52, longitude_max=4)
    sites = get_sites_from_user(session=db_session, user=user_with_sites, lat_lon_limits=lat_lon)
    assert len(sites) > 0


def test_get_site_list_min(db_session, user_with_sites):
    # examples sites are at 51,3
    lat_lon = LatitudeLongitudeLimits(latitude_min=52, longitude_min=2)
    sites = get_sites_from_user(session=db_session, user=user_with_sites, lat_lon_limits=lat_lon)
    assert len(sites) == 0

    lat_lon = LatitudeLongitudeLimits(latitude_min=50, longitude_min=4)
    sites = get_sites_from_user(session=db_session, user=user_with_sites, lat_lon_limits=lat_lon)
    assert len(sites) == 0

    lat_lon = LatitudeLongitudeLimits(latitude_min=50, longitude_min=2)
    sites = get_sites_from_user(session=db_session, user=user_with_sites, lat_lon_limits=lat_lon)
    assert len(sites) > 0
